"""SensorProvider real para Windows (psutil + PDH + DXGI + D3DKMT + NVML)."""

import functools
import logging
import socket
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

import psutil

from pcx_agent.ratelimit_log import RateLimitedLog
from pcx_agent.sensors.base import DiskVolume, GpuReading, Snapshot
from pcx_agent.sensors.windows import d3dkmt, native
from pcx_agent.sensors.windows.gpu import (
    AdapterInfo,
    describe_adapters,
    luid_of,
    parse_gpu_usage,
    parse_vram_usage,
    temperature_sources,
)

logger = logging.getLogger("pcx_agent.sensors.windows")
ADAPTER_CACHE_S = 60.0
RETRY_S = 60.0
MAX_INSTANCES = 500


def _locked(method):
    """Serializa o metodo com os demais: o sampler le numa thread e a janela reinicia noutra."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


def _pct(value: float) -> float:
    return min(100.0, max(0.0, float(value)))


class WindowsSensorProvider:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        psutil.cpu_percent(interval=None)  # a primeira chamada devolve 0 e serve de referencia
        self._net = psutil.net_io_counters()
        self._disk_io = psutil.disk_io_counters()
        self._last = time.monotonic()
        # Falhas repetidas da GPU: no maximo uma linha por minuto por tipo.
        self._failures = RateLimitedLog(logger, interval_s=60.0, clock=clock)
        # A bandeja liga aqui a verificacao dos sensores; chamado so quando a falha vai para o log.
        self.on_sensor_failure: Callable[[], None] | None = None
        self._adapters: dict[str, AdapterInfo] = {}
        # Temperatura de alerta por LUID: lida uma vez por lista de placas, nao a cada leitura.
        self._warnings: dict[str, float] = {}
        self._logged_adapters: dict[str, AdapterInfo] | None = None
        # Fonte da temperatura por LUID ("driver", "nvml" ou "nenhuma"), para o log e o relatorio.
        self.temperature_source: dict[str, str] = {}
        self._logged_sources: dict[str, str] | None = None
        # Nomes das instancias do ultimo contador de GPU, para o relatorio do diagnostico.
        self.gpu_instances: list[str] = []
        self._adapters_at = float("-inf")
        self._pdh = self._open(native.PdhGpuCounters, "contadores de GPU")
        self._nvml = self._open(native.NvmlTemperatures, "temperatura NVIDIA (NVML)")
        self._d3d = self._open(d3dkmt.D3dkmtTemperatures, "temperatura pelo driver (D3DKMT)")
        self._pdh_retry_at = clock() + RETRY_S
        self._nvml_retry_at = clock() + RETRY_S
        self._d3d_retry_at = clock() + RETRY_S
        # O hello pode vir antes da 1a leitura: a sondagem acontece aqui, na thread de quem cria
        # o provider, e nunca dentro de capabilities() (chamado no laco do servidor).
        self._driver_has_temp = False
        if self._d3d is not None:
            self._probe_driver_temperature()

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
        if self._d3d is None and now >= self._d3d_retry_at:
            self._d3d = self._open(d3dkmt.D3dkmtTemperatures, "D3DKMT", quiet=True)
            self._d3d_retry_at = now + RETRY_S
            self._load_warnings()

    def _report_failure(self, key: str, msg: str, *args: object, exc_info: bool = False) -> None:
        logged = self._failures.report(key, msg, *args, exc_info=exc_info)
        callback = self.on_sensor_failure
        if logged and callback is not None:
            try:
                callback()
            except Exception:
                logger.debug("on_sensor_failure falhou", exc_info=True)

    @_locked
    def adapter_drivers(self) -> dict[str, str | None]:
        """Versao do driver de cada placa, por LUID (a mesma chave de `temperature_source`)."""
        return {key: info.driver_version for key, info in self._adapters.items()}

    @_locked
    def reset_sensors(self) -> None:
        """Fecha e reabre PDH, NVML e D3DKMT na hora (correcao "Reiniciar sensores")."""
        self.close()
        self._pdh = self._open(native.PdhGpuCounters, "contadores de GPU")
        self._nvml = self._open(native.NvmlTemperatures, "temperatura NVIDIA (NVML)")
        self._d3d = self._open(d3dkmt.D3dkmtTemperatures, "temperatura pelo driver (D3DKMT)")
        now = self._clock()
        self._pdh_retry_at = self._nvml_retry_at = self._d3d_retry_at = now + RETRY_S
        self._adapters_at = float("-inf")
        self._warnings = {}
        self._driver_has_temp = False
        if self._d3d is not None:
            self._probe_driver_temperature()

    @_locked
    def capabilities(self) -> set[str]:
        caps = {"cpu", "ram", "disk", "net"}
        if self._pdh is not None:
            caps.add("gpu")
        if self._nvml is not None or self._driver_has_temp:
            caps.add("gpu.temp")
        return caps

    def _refresh_adapters(self) -> None:
        now = self._clock()
        if now - self._adapters_at >= ADAPTER_CACHE_S:
            self._adapters = native.list_adapters()
            self._adapters_at = now
            self._log_adapters()
            self._load_warnings()

    def _boards(self) -> str:
        """Nomes das placas conhecidas, para as mensagens de falha."""
        names = [info.name for info in self._adapters.values()]
        return ", ".join(names) if names else "placa desconhecida"

    def _load_warnings(self) -> None:
        """Le a temperatura de alerta de cada placa; falha aqui nunca derruba a leitura."""
        self._warnings = {}
        if self._d3d is None:
            return
        try:
            self._warnings = self._d3d.read_warnings(list(self._adapters))
        except Exception:  # noqa: BLE001 - opcional; registrado pelo RateLimitedLog
            self._report_failure(
                "d3dkmt_caps",
                "Falha ao ler a temperatura de alerta (D3DKMT) de %s",
                self._boards(),
                exc_info=True,
            )

    def _probe_driver_temperature(self) -> None:
        try:
            self._refresh_adapters()
        except Exception:  # noqa: BLE001 - a leitura normal registra a falha
            return
        self._driver_temperatures()

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

    def _driver_temperatures(self) -> dict[str, float]:
        """{LUID: C} pelo driver de video; vale para NVIDIA, AMD e Intel."""
        if self._d3d is None:
            return {}
        try:
            temps = self._d3d.read(list(self._adapters))
        except Exception:  # noqa: BLE001 - registrado com o traceback pelo RateLimitedLog
            self._report_failure(
                "d3dkmt",
                "Falha ao ler a temperatura (D3DKMT) de %s; tentando de novo em 60 s",
                self._boards(),
                exc_info=True,
            )
            self._drop("_d3d", "D3DKMT")
            return {}
        self._driver_has_temp = bool(temps)
        return temps

    def _temperatures(self) -> dict[str, float]:
        if self._nvml is None:
            return {}
        try:
            return self._nvml.read()
        except Exception:  # noqa: BLE001 - registrado com o traceback pelo RateLimitedLog
            self._report_failure(
                "nvml",
                "Falha ao ler a temperatura (NVML) de %s; tentando de novo em 60 s",
                self._boards(),
                exc_info=True,
            )
            self._drop("_nvml", "NVML")
            return {}

    def _log_adapters(self) -> None:
        """Uma linha por placa ao abrir e quando a lista muda (placa nova, driver trocado)."""
        if self._adapters == self._logged_adapters:
            return
        self._logged_adapters = dict(self._adapters)
        lines = describe_adapters(self._adapters)
        if not lines:
            logger.info("Nenhuma placa de video encontrada (DXGI)")
        for line in lines:
            logger.info("Placa de video: %s", line)

    def _log_temperature_sources(self, sources: dict[str, str]) -> None:
        """Uma linha por placa na primeira leitura e quando a fonte da temperatura muda."""
        self.temperature_source = sources
        if sources == self._logged_sources:
            return
        self._logged_sources = dict(sources)
        for luid, source in sources.items():
            info = self._adapters.get(luid)
            logger.info("Temperatura de %s: %s", info.name if info else luid, source)

    def _gpus(self) -> list[GpuReading]:
        self._maybe_reopen()
        if self._pdh is None:
            return []
        try:
            self._refresh_adapters()
            engines, memory = self._pdh.read()
            self.gpu_instances = [str(sample.get("InstanceName", "")) for sample in engines[:MAX_INSTANCES]]
            readings = parse_gpu_usage(engines, self._adapters, parse_vram_usage(memory))
        except Exception:  # noqa: BLE001 - registrado com o traceback pelo RateLimitedLog
            self._report_failure(
                "gpu", "Falha ao ler a GPU (PDH); tentando de novo em 60 s", exc_info=True
            )
            self._drop("_pdh", "contadores de GPU")
            return []
        # A temperatura e opcional: se falhar, o uso e a VRAM continuam aparecendo.
        # Primeiro o driver (por LUID, duas placas iguais nao se confundem); o NVML completa.
        by_luid = self._driver_temperatures()
        by_name = self._temperatures()
        self._log_temperature_sources(temperature_sources(readings, by_luid, by_name))
        return [
            r.model_copy(
                update={
                    "temp_c": by_luid.get(luid_of(r.id), by_name.get(r.name)),
                    "temp_warn_c": self._warnings.get(luid_of(r.id)),
                }
            )
            for r in readings
        ]

    @_locked
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

    @_locked
    def close(self) -> None:
        for resource in (self._pdh, self._nvml, self._d3d):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    logger.debug("Falha ao fechar um sensor", exc_info=True)
        self._pdh = self._nvml = self._d3d = None
