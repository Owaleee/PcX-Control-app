"""Roda todas as verificacoes: cada uma protegida, cada resultado registrado no log."""

import json
import logging
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from pcx_agent.diagnostics import checks
from pcx_agent.diagnostics.model import (
    GROUP_AGENT,
    GROUP_ANTIVIRUS,
    GROUP_NETWORK,
    GROUP_SENSORS,
    AgentProbe,
    CheckResult,
    FirewallRule,
    SecurityProduct,
)
from pcx_agent.network import NetInterface, choose_lan
from pcx_agent.sensors.base import GpuReading, Snapshot

logger = logging.getLogger("pcx_agent.diagnostics")
PROBE_TIMEOUT_S = 3.0
# Verificacoes baratas, sem PowerShell nem rede: rodam logo e a qualquer hora.
QUICK_CHECKS = frozenset({"rede.ip", "rede.tipo", "sensores.leitura"})


@dataclass(frozen=True)
class Sources:
    """De onde vem cada dado. Injetavel: os testes passam funcoes falsas."""

    interfaces: Callable[[], list[NetInterface]]
    route: Callable[[], str | None]
    profiles: Callable[[], dict[str, str] | None]
    firewall_rules: Callable[[], list[FirewallRule] | None]
    exe_path: Callable[[], str | None]
    security: Callable[[], list[SecurityProduct] | None]
    probe: Callable[[str], AgentProbe]
    reading: Callable[[], tuple[Snapshot | None, str | None]]
    port: int
    reading_age: Callable[[], float | None] = lambda: None
    # (erro de inicio do servidor, servidor rodando)
    server_state: Callable[[], tuple[str | None, bool]] = lambda: (None, True)


def probe_agent(address: str, agent_id: str, timeout: float = PROBE_TIMEOUT_S) -> AgentProbe:
    """Chama /v1/info pelo IP da rede, de dentro do PC, e confere se e este agente."""
    # Sem proxy: num PC de empresa, o proxy do Windows tambem pegaria o IP da rede local.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://{address}/v1/info", timeout=timeout) as response:
            info = json.loads(response.read())
    except urllib.error.HTTPError:
        return AgentProbe(reachable=True, same_agent=False)  # respondeu, mas nao e o agente
    except (OSError, ValueError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        return AgentProbe(reachable=False, error=str(reason))
    same = isinstance(info, dict) and info.get("agent_id") == agent_id
    return AgentProbe(reachable=True, same_agent=same)


def exe_path() -> str | None:
    """Caminho do .exe instalado; None rodando pelo codigo (sem regra de firewall do instalador)."""
    return sys.executable if getattr(sys, "frozen", False) else None


def _guarded(check_id: str, group: str, title: str, run: Callable[[], list[CheckResult]]) -> list[CheckResult]:
    try:
        return run()
    except Exception as exc:
        logger.warning("Verificacao %s falhou", check_id, exc_info=True)
        return [CheckResult(check_id, group, title, "info", f"Não deu para verificar: {type(exc).__name__}: {exc}")]


def run_all(sources: Sources, only: set[str] | None = None) -> list[CheckResult]:
    interfaces = _guarded_value(sources.interfaces, [])
    chosen = choose_lan(interfaces, preferred=_guarded_value(sources.route, None))
    address = f"{chosen.ipv4 if chosen else '127.0.0.1'}:{sources.port}"

    def reading() -> list[CheckResult]:
        snapshot, error = sources.reading()
        return checks.check_reading(snapshot, error, age_s=sources.reading_age())

    def gpus() -> list[CheckResult]:
        snapshot, _ = sources.reading()
        gpu_list: list[GpuReading] = snapshot.gpus if snapshot is not None else []
        return checks.check_gpus(gpu_list)

    def agent() -> list[CheckResult]:
        server_error, server_running = sources.server_state()
        return checks.check_agent(sources.probe(address), address, server_error, server_running)

    plan = [
        ("rede.ip", GROUP_NETWORK, "IP da rede local", lambda: checks.check_ip(interfaces, chosen)),
        ("rede.tipo", GROUP_NETWORK, "Tipo de rede no Windows", lambda: checks.check_network_type(chosen, sources.profiles())),
        ("rede.firewall", GROUP_NETWORK, "Regra do firewall", lambda: checks.check_firewall(sources.firewall_rules(), sources.exe_path())),
        ("rede.vpn", GROUP_NETWORK, "VPN", lambda: checks.check_vpn(interfaces)),
        ("agente.local", GROUP_AGENT, "Agente respondendo na rede", agent),
        ("antivirus.terceiros", GROUP_ANTIVIRUS, "Antivírus e firewall de terceiros", lambda: checks.check_antivirus(sources.security())),
        ("sensores.gpu", GROUP_SENSORS, "Placa de vídeo", gpus),
        ("sensores.leitura", GROUP_SENSORS, "Leitura dos sensores", reading),
    ]
    results: list[CheckResult] = []
    for check_id, group, title, run in plan:
        if only is not None and check_id not in only:
            continue
        results.extend(_guarded(check_id, group, title, run))
    for result in results:
        logger.info("Diagnostico %s (%s): %s - %s", result.id, result.title, result.status, result.detail)
    return results


def _guarded_value(read, default):
    try:
        return read()
    except Exception:
        logger.warning("Leitura do diagnostico falhou", exc_info=True)
        return default
