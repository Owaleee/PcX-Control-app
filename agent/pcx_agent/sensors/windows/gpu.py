"""Interpretacao pura dos contadores de GPU do Windows (testavel em qualquer sistema)."""

import math
import re
from dataclasses import dataclass

from pcx_agent.sensors.base import GpuReading

# \GPU Engine(*)\Utilization Percentage -> pid_X_luid_0xH_0xL_phys_N_eng_M_engtype_T[#k]
_ENGINE = re.compile(
    r"^pid_\d+_luid_(0x[0-9a-f]+_0x[0-9a-f]+)_phys_(\d+)_eng_(\d+)_engtype_(.+)$",
    re.IGNORECASE,
)
# \GPU Adapter Memory(*)\Dedicated Usage -> luid_0xH_0xL_phys_N
_MEMORY = re.compile(r"^luid_(0x[0-9a-f]+_0x[0-9a-f]+)_phys_(\d+)$", re.IGNORECASE)


_VENDORS = {0x10DE: "nvidia", 0x1002: "amd", 0x8086: "intel"}
GIB = 1024**3


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    vram_total_bytes: int
    vendor_id: int = 0


def vendor_name(vendor_id: int) -> str:
    """Fabricante pelo `VendorId` do PCI: so para logs e relatorio, o app nao mostra."""
    return _VENDORS.get(vendor_id, "outra")


def _dedicated_first(item: tuple[str, AdapterInfo]) -> tuple[int, str]:
    """Mais VRAM dedicada primeiro: a placa dedicada vem antes da integrada."""
    key, info = item
    return (-info.vram_total_bytes, key)


def describe_adapters(adapters: dict[str, AdapterInfo]) -> list[str]:
    """Uma linha por placa para o log, na mesma ordem em que o app recebe as placas."""
    return [
        f"{info.name} | fabricante {vendor_name(info.vendor_id)} (VendorId 0x{info.vendor_id:04X}) "
        f"| VRAM {info.vram_total_bytes / GIB:.1f} GiB | LUID {luid}"
        for luid, info in sorted(adapters.items(), key=_dedicated_first)
    ]


def _valid(value: object) -> bool:
    return isinstance(value, int | float) and math.isfinite(value) and value >= 0


def adapter_key(luid: str, phys: str | int) -> str:
    return f"luid_{luid.lower()}_phys_{phys}"


def parse_gpu_usage(
    samples: list[dict],
    adapters: dict[str, AdapterInfo],
    vram_used: dict[str, int] | None = None,
) -> list[GpuReading]:
    """Uso por placa: soma por motor entre processos e devolve o motor mais ocupado.

    Motores de video (NVIDIA "VideoDecode"/"VideoEncode", AMD "video codec 0") ficam de fora:
    gravar a tela ou tocar video ocupa o codificador sem ser o "uso da GPU" que o Gerenciador de
    Tarefas mostra por padrao (3D, Copy, Compute).

    As placas saem com a de mais VRAM dedicada primeiro: e a primeira que o app mostra no painel.

    `adapters` e indexado pelo LUID DXGI (minusculo); LUIDs que nao estao la
    (adaptador de software, removido) sao ignorados.
    """
    engines: dict[str, dict[str, float]] = {}
    luids: dict[str, str] = {}
    for sample in samples:
        match = _ENGINE.match(str(sample.get("InstanceName", "")))
        value = sample.get("CookedValue")
        if match is None or not _valid(value):
            continue
        luid, phys, engine = match.group(1).lower(), match.group(2), match.group(3)
        if luid not in adapters:
            continue
        key = adapter_key(luid, phys)
        luids[key] = luid
        per_engine = engines.setdefault(key, {})
        if match.group(4).strip().lower().startswith("video"):
            continue  # a placa aparece, mas o motor de video nao conta no uso
        per_engine[engine] = per_engine.get(engine, 0.0) + float(value)

    readings = []
    order = sorted(engines, key=lambda k: (-adapters[luids[k]].vram_total_bytes, k))
    for key in order:
        info = adapters[luids[key]]
        used = (vram_used or {}).get(key)
        readings.append(
            GpuReading(
                id=key,
                name=info.name,
                usage_percent=round(min(100.0, max(engines[key].values(), default=0.0)), 2),
                vram_used_bytes=int(used) if used is not None else None,
                vram_total_bytes=info.vram_total_bytes or None,
                vendor=vendor_name(info.vendor_id),
            )
        )
    return readings


def parse_vram_usage(samples: list[dict]) -> dict[str, int]:
    """Memoria dedicada em uso, por placa, a partir de \\GPU Adapter Memory(*)."""
    result: dict[str, int] = {}
    for sample in samples:
        match = _MEMORY.match(str(sample.get("InstanceName", "")))
        value = sample.get("CookedValue")
        if match is not None and _valid(value):
            result[adapter_key(match.group(1), match.group(2))] = int(value)
    return result
