"""Modelos de leitura e a interface dos provedores de sensores."""

from datetime import datetime
from typing import Annotated, Protocol

from pydantic import BaseModel, Field

Percent = Annotated[float, Field(ge=0, le=100)]
NonNegative = Annotated[float, Field(ge=0)]


class GpuReading(BaseModel):
    id: str
    name: str
    usage_percent: Percent
    vram_used_bytes: int | None = None
    vram_total_bytes: int | None = None
    temp_c: float | None = None


class DiskVolume(BaseModel):
    mount: str
    percent: Percent
    used_bytes: int = Field(ge=0)
    total_bytes: int = Field(ge=0)


class Snapshot(BaseModel):
    t: datetime
    cpu_total: Percent
    ram_percent: Percent
    ram_used_bytes: int = Field(ge=0)
    ram_total_bytes: int = Field(ge=0)
    disks: list[DiskVolume]
    disk_read_bps: NonNegative
    disk_write_bps: NonNegative
    net_down_bps: NonNegative
    net_up_bps: NonNegative
    gpus: list[GpuReading]
    host_name: str
    uptime_s: NonNegative

    def metrics(self) -> dict[str, float]:
        """Valores numericos planos usados no historico."""
        values: dict[str, float] = {
            "cpu.total": self.cpu_total,
            "ram.percent": self.ram_percent,
            "net.down_bps": self.net_down_bps,
            "net.up_bps": self.net_up_bps,
            "disk.read_bps": self.disk_read_bps,
            "disk.write_bps": self.disk_write_bps,
        }
        if self.gpus:
            gpu = self.gpus[0]
            values["gpu.usage"] = gpu.usage_percent
            if gpu.temp_c is not None:
                values["gpu.temp"] = gpu.temp_c
            if gpu.vram_used_bytes is not None and gpu.vram_total_bytes:
                values["gpu.vram_percent"] = 100.0 * gpu.vram_used_bytes / gpu.vram_total_bytes
        return values


class SensorProvider(Protocol):
    def capabilities(self) -> set[str]: ...

    def read(self) -> Snapshot: ...

    def close(self) -> None: ...
