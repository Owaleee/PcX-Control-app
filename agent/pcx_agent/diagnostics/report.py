"""Texto do "Copiar relatorio": o que a pessoa manda para quem esta ajudando."""

import re
from dataclasses import dataclass, field

from pcx_agent.diagnostics.checks import VENDOR_LABELS, _is_vpn
from pcx_agent.diagnostics.model import GROUPS, CheckResult
from pcx_agent.logs import redact
from pcx_agent.network import NetInterface, is_virtual
from pcx_agent.sensors.base import GpuReading

STATUS_LABELS = {"ok": "OK", "atencao": "ATENÇÃO", "problema": "PROBLEMA", "info": "INFO"}
_ENGINE = re.compile(r"luid_(0x[0-9a-f]+_0x[0-9a-f]+)_phys_(\d+)_eng_\d+_engtype_(.+?)(?:#\d+)?$", re.IGNORECASE)


@dataclass(frozen=True)
class ReportFacts:
    agent_version: str
    windows_version: str
    interfaces: list[NetInterface] = field(default_factory=list)
    gpus: list[GpuReading] = field(default_factory=list)
    pdh_instances: list[str] = field(default_factory=list)


def engine_types(instances: list[str]) -> dict[str, list[str]]:
    """Nomes das instancias PDH -> {placa: tipos de motor}. Sem pid e sem repeticao.

    Os nomes inteiros nao entram no relatorio: sao longos o bastante para o filtro de segredos
    esconder, e o que importa para tratar uma placa nova e o tipo de motor que ela expoe.
    """
    found: dict[str, set[str]] = {}
    for name in instances:
        match = _ENGINE.search(name)
        if match:
            card = f"LUID {match.group(1).lower()} phys {match.group(2)}"
            found.setdefault(card, set()).add(match.group(3).strip())
    return {card: sorted(kinds, key=str.lower) for card, kinds in sorted(found.items())}


def build_report(results: list[CheckResult], facts: ReportFacts) -> str:
    lines = [
        f"PcX Control {facts.agent_version} - relatório de diagnóstico",
        f"Windows: {facts.windows_version}",
        "",
    ]
    for group in GROUPS:
        items = [r for r in results if r.group == group]
        if not items:
            continue
        lines.append(f"[{group}]")
        lines.extend(f"- {STATUS_LABELS[r.status]} | {r.title}: {r.detail}" for r in items)
        lines.append("")
    lines.append("[Placas de rede]")
    for i in facts.interfaces:
        kind = "VPN" if _is_vpn(i) else "virtual" if is_virtual(i.name, i.ipv4) else "rede"
        lines.append(f"- {i.name}: {i.ipv4} | {'ligada' if i.up else 'desligada'} | {kind}")
    lines.append("")
    lines.append("[Placas de vídeo]")
    for gpu in facts.gpus:
        vram = f"{gpu.vram_total_bytes / 1024**3:.1f} GiB" if gpu.vram_total_bytes else "VRAM desconhecida"
        temp = f"{gpu.temp_c:.0f} °C" if gpu.temp_c is not None else "sem temperatura"
        vendor = VENDOR_LABELS.get(gpu.vendor or "", "outro")
        luid = gpu.id.removeprefix("luid_").replace("_phys_", " phys ")
        lines.append(f"- {gpu.name} | {vendor} | {vram} | uso {gpu.usage_percent:.0f}% | {temp} | LUID {luid}")
    for card, kinds in engine_types(facts.pdh_instances).items():
        lines.append(f"- Motores de {card}: {', '.join(kinds)}")
    # Nunca sai senha, codigo ou token: o mesmo filtro do log passa no texto inteiro.
    return redact("\n".join(lines).rstrip() + "\n")
