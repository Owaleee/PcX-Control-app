"""Sensor simulado: testes, Linux, Docker e modo demo."""

import math
import random
from datetime import UTC, datetime

from pcx_agent.sensors.base import DiskVolume, GpuReading, Snapshot

GIB = 1024**3


class FakeSensorProvider:
    """Valores que oscilam de forma suave e previsivel para uma mesma seed."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._phase = self._rng.uniform(0, 2 * math.pi)
        self._step = 0

    def capabilities(self) -> set[str]:
        return {"cpu", "ram", "disk", "net", "gpu", "gpu.temp"}

    def _wave(self, low: float, high: float, speed: float = 0.2) -> float:
        middle = (low + high) / 2
        amplitude = (high - low) / 2
        noise = self._rng.uniform(-0.02, 0.02) * amplitude
        value = middle + amplitude * math.sin(self._phase + self._step * speed) + noise
        return min(high, max(low, value))

    def read(self) -> Snapshot:
        ram_total = 32 * GIB
        ram_percent = self._wave(40, 70, 0.05)
        vram_total = 8 * GIB
        vram_used = int(vram_total * self._wave(20, 60, 0.07) / 100)
        snapshot = Snapshot(
            t=datetime.now(UTC),
            cpu_total=self._wave(5, 80),
            ram_percent=ram_percent,
            ram_used_bytes=int(ram_total * ram_percent / 100),
            ram_total_bytes=ram_total,
            disks=[
                DiskVolume(mount="C:\\", percent=65.0, used_bytes=600 * GIB, total_bytes=930 * GIB),
                DiskVolume(mount="D:\\", percent=40.0, used_bytes=400 * GIB, total_bytes=1000 * GIB),
            ],
            disk_read_bps=self._wave(0, 80e6, 0.3),
            disk_write_bps=self._wave(0, 40e6, 0.3),
            net_down_bps=self._wave(0, 12e6, 0.15),
            net_up_bps=self._wave(0, 1e6, 0.15),
            gpus=[
                GpuReading(
                    id="luid_0x00000000_0x0000d1a5_phys_0",
                    name="GPU Simulada",
                    usage_percent=self._wave(0, 95, 0.1),
                    vram_used_bytes=vram_used,
                    vram_total_bytes=vram_total,
                    temp_c=self._wave(40, 75, 0.04),
                )
            ],
            host_name="PC-DEMO",
            uptime_s=3600.0 + self._step,
        )
        self._step += 1
        return snapshot

    def close(self) -> None:
        return None
