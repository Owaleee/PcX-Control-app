"""Tipos do diagnostico: o resultado de cada verificacao e os dados lidos do Windows."""

from dataclasses import dataclass
from typing import Literal

Status = Literal["ok", "atencao", "problema", "info"]
Fix = Literal["abrir_rede", "criar_firewall"]

GROUP_NETWORK = "Rede e firewall"
GROUP_AGENT = "Agente acessível"
GROUP_ANTIVIRUS = "Antivírus"
GROUP_SENSORS = "Sensores"
GROUPS = (GROUP_NETWORK, GROUP_AGENT, GROUP_ANTIVIRUS, GROUP_SENSORS)


@dataclass(frozen=True)
class CheckResult:
    id: str
    group: str
    title: str
    status: Status
    detail: str
    fix: Fix | None = None


@dataclass(frozen=True)
class FirewallRule:
    name: str
    enabled: bool
    direction: str  # "in" ou "out"
    action: str  # "allow" ou "block"
    profiles: frozenset[str]  # "private", "public", "domain" ou "any"
    program: str | None


@dataclass(frozen=True)
class SecurityProduct:
    name: str
    kind: str  # "antivirus" ou "firewall"
    enabled: bool
    from_windows: bool


@dataclass(frozen=True)
class AgentProbe:
    """Resultado de chamar o proprio agente pelo IP da rede, de dentro do PC."""

    reachable: bool
    same_agent: bool = False
    error: str | None = None
