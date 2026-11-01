"""SensorProvider real para Windows (psutil + PDH + DXGI + NVML)."""

import logging
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime

import psutil

from pcx_agent.sensors.base import DiskVolume, GpuReading, Snapshot
from pcx_agent.sensors.windows import native
from pcx_agent.sensors.windows.gpu import AdapterInfo, parse_gpu_usage, parse_vram_usage

logger = logging.getLogger("pcx_agent.sensors.windows")
ADAPTER_CACHE_S = 60.0
RETRY_S = 60.0


def _pct(value: float) -> float:
    return min(100.0, max(0.0, float(value)))


class WindowsSensorProvider:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        psutil.cpu_percent(interval=None)  # a primeira chamada devolve 0 e serve de referencia
        self._net = psutil.net_io_counters()
        self._disk_io = psutil.disk_io_counters()
        self._last = time.monotonic()
        self._gpu_failed_once = False
        self._adapters: dict[str, AdapterInfo] = {}
        self._adapters_at = float("-inf")
        self._pdh = self._open(native.PdhGpuCounters, "contadores de GPU")
        self._nvml = self._open(native.NvmlTemperatures, "temperatura NVIDIA (NVML)")
        self._pdh_retry_at = clock() + RETRY_S
        self._nvml_retry_at = clock() + RETRY_S

    @staticmethod
    def _open(factory, label: str, quiet: bool = False):
        try:
            return factory()
        except Exception as exc:  # noqa: BLE001 - recurso opcional
            logger.log(logging.DEBUG if quiet else logging.INFO, "Sem %s: %s", label, exc)
            return None

    def _drop(self, name: str, label: str) -> None:
        """Fecha um recurso que falhou e agenda nova tentativa (driver reiniciado, por exemplo)."""
        resource = getattr(self, name)
        setattr(self, name, None)
        setattr(self, f"{name}_retry_at", self._clock() + RETRY_S)
        if resource is not None:
            try:
                resource.close()
            except Exception:
                logger.debug("Falha ao fechar %s", label, exc_info=True)

    def _maybe_reopen(self) -> None:
        now = self._clock()
        if self._pdh is None and now >= self._pdh_retry_at:
            self._pdh = self._open(native.PdhGpuCounters, "contadores de GPU", quiet=True)
            self._pdh_retry_at = now + RETRY_S
        if self._nvml is None and now >= self._nvml_retry_at:
            self._nvml = self._open(native.NvmlTemperatures, "NVML", quiet=True)
            self._nvml_retry_at = now + RETRY_S

    def capabilities(self) -> set[str]:
        caps = {"cpu", "ram", "disk", "net"}
        if self._pdh is not None:
            caps.add("gpu")
        if self._nvml is not None:
            caps.add("gpu.temp")
        return caps

    def _volumes(self) -> list[DiskVolume]:
        volumes = []
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in part.opts or not part.fstype:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            volumes.append(
                DiskVolume(
                    mount=part.mountpoint,
                    percent=_pct(usage.percent),
                    used_bytes=usage.used,
                    total_bytes=usage.total,
                )
            )
        return volumes

    def _temperatures(self) -> dict[str, float]:
        if self._nvml is None:
            return {}
        try:
            return self._nvml.read()
        except Exception:
            logger.warning("Falha ao ler a temperatura (NVML); tentando de novo em 60 s", exc_info=True)
            self._drop("_nvml", "NVML")
            return {}

    def _gpus(self) -> list[GpuReading]:
        self._maybe_reopen()
        if self._pdh is None:
            return []
        try:
            now = self._clock()
            if now - self._adapters_at >= ADAPTER_CACHE_S:
                self._adapters = native.list_adapters()
                self._adapters_at = now
            engines, memory = self._pdh.read()
            readings = parse_gpu_usage(engines, self._adapters, parse_vram_usage(memory))
        except Exception:
            level = logging.DEBUG if self._gpu_failed_once else logging.WARNING
            logger.log(level, "Falha ao ler a GPU; tentando de novo em 60 s", exc_info=True)
            self._gpu_failed_once = True
            self._drop("_pdh", "contadores de GPU")
            return []
        # A temperatura e opcional: se falhar, o uso e a VRAM continuam aparecendo.
        temps = self._temperatures()
        return [r.model_copy(update={"temp_c": temps.get(r.name)}) for r in readings]

    def read(self) -> Snapshot:
        now = time.monotonic()
        elapsed = max(now - self._last, 1e-3)
        net, disk_io = psutil.net_io_counters(), psutil.disk_io_counters()
        down = max(0.0, (net.bytes_recv - self._net.bytes_recv) / elapsed)
        up = max(0.0, (net.bytes_sent - self._net.bytes_sent) / elapsed)
        read_bps = write_bps = 0.0
        if disk_io is not None and self._disk_io is not None:
            read_bps = max(0.0, (disk_io.read_bytes - self._disk_io.read_bytes) / elapsed)
            write_bps = max(0.0, (disk_io.write_bytes - self._disk_io.write_bytes) / elapsed)
        self._net, self._disk_io, self._last = net, disk_io, now

        memory = psutil.virtual_memory()
        return Snapshot(
            t=datetime.now(UTC),
            cpu_total=_pct(psutil.cpu_percent(interval=None)),
            ram_percent=_pct(memory.percent),
            ram_used_bytes=memory.total - memory.available,
            ram_total_bytes=memory.total,
            disks=self._volumes(),
            disk_read_bps=read_bps,
            disk_write_bps=write_bps,
            net_down_bps=down,
            net_up_bps=up,
            gpus=self._gpus(),
            host_name=socket.gethostname(),
            uptime_s=max(0.0, time.time() - psutil.boot_time()),
        )

    def close(self) -> None:
        for resource in (self._pdh, self._nvml):
            if resource is not None:
                resource.close()
