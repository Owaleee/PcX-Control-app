"""SensorProvider real para Windows (psutil + PDH + DXGI + NVML)."""

import logging
import socket
import time
from datetime import UTC, datetime

import psutil

from pcx_agent.sensors.base import DiskVolume, GpuReading, Snapshot
from pcx_agent.sensors.windows import native
from pcx_agent.sensors.windows.gpu import AdapterInfo, parse_gpu_usage, parse_vram_usage

logger = logging.getLogger("pcx_agent.sensors.windows")
ADAPTER_CACHE_S = 60.0


def _pct(value: float) -> float:
    return min(100.0, max(0.0, float(value)))


class WindowsSensorProvider:
    def __init__(self) -> None:
        psutil.cpu_percent(interval=None)  # a primeira chamada devolve 0 e serve de referencia
        self._net = psutil.net_io_counters()
        self._disk_io = psutil.disk_io_counters()
        self._last = time.monotonic()
        self._gpu_failed_once = False
        self._adapters: dict[str, AdapterInfo] = {}
        self._adapters_at = float("-inf")
        self._pdh = self._open(native.PdhGpuCounters, "contadores de GPU")
        self._nvml = self._open(native.NvmlTemperatures, "temperatura NVIDIA (NVML)")

    @staticmethod
    def _open(factory, label: str):
        try:
            return factory()
        except Exception as exc:  # noqa: BLE001 - recurso opcional
            logger.info("Sem %s neste PC: %s", label, exc)
            return None

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

    def _gpus(self) -> list[GpuReading]:
        if self._pdh is None:
            return []
        try:
            now = time.monotonic()
            if now - self._adapters_at >= ADAPTER_CACHE_S:
                self._adapters = native.list_adapters()
                self._adapters_at = now
            engines, memory = self._pdh.read()
            readings = parse_gpu_usage(engines, self._adapters, parse_vram_usage(memory))
            temps = self._nvml.read() if self._nvml is not None else {}
            return [r.model_copy(update={"temp_c": temps.get(r.name)}) for r in readings]
        except Exception:
            level = logging.DEBUG if self._gpu_failed_once else logging.WARNING
            logger.log(level, "Falha ao ler a GPU", exc_info=True)
            self._gpu_failed_once = True
            return []

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
