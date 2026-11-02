"""Rede do PC: qual IP vai no QR e se a rede esta como Publica no Windows.

A rota padrao (pairing_uri.local_ipv4) pode passar por uma VPN, como a Radmin; o celular
nunca alcanca esse IP. Aqui escolhemos a placa da rede local.
"""

import ipaddress
import json
import logging
import subprocess
import sys
from dataclasses import dataclass

import psutil

from pcx_agent.pairing_uri import local_ipv4

logger = logging.getLogger("pcx_agent.network")

# Nomes de placas de VPN e virtuais (comparacao sem maiusculas).
VIRTUAL_NAMES = (
    "radmin", "hamachi", "zerotier", "tailscale", "wireguard", "openvpn", "tap-windows", "tap ",
    "vpn", "vethernet", "hyper-v", "virtualbox", "vmware", "wsl", "loopback", "teredo",
    "bluetooth", "docker", "npcap",
)
VIRTUAL_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in ("26.0.0.0/8", "25.0.0.0/8", "100.64.0.0/10", "169.254.0.0/16", "127.0.0.0/8")
)
# Ordem de preferencia entre as faixas privadas quando nao ha dica da rota.
LAN_NETWORKS = tuple(
    ipaddress.ip_network(n) for n in ("192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12")
)
CATEGORIES = {0: "public", 1: "private", 2: "domain"}
PROFILE_TIMEOUT_S = 5.0
IS_WINDOWS = sys.platform == "win32"
# O PowerShell 5.1 escreve na pagina de codigo do console (cp850 em pt-BR): forca UTF-8 para
# nomes com acento ("Conexao Local" com til) baterem com os do psutil.
PROFILE_SCRIPT = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    "Get-NetConnectionProfile | Select-Object InterfaceAlias,NetworkCategory | ConvertTo-Json"
)


@dataclass(frozen=True)
class NetInterface:
    name: str
    ipv4: str
    up: bool


def is_virtual(name: str, ipv4: str) -> bool:
    lowered = name.lower()
    if any(word in lowered for word in VIRTUAL_NAMES):
        return True
    address = ipaddress.ip_address(ipv4)
    return any(address in network for network in VIRTUAL_NETWORKS)


def _lan_rank(ipv4: str) -> int | None:
    address = ipaddress.ip_address(ipv4)
    for rank, network in enumerate(LAN_NETWORKS):
        if address in network:
            return rank
    return None


def choose_lan(interfaces: list[NetInterface], preferred: str | None) -> NetInterface | None:
    """A placa ativa, real e com IP privado; a da rota padrao vence, depois 192.168 > 10 > 172."""
    candidates = [
        i for i in interfaces
        if i.up and not is_virtual(i.name, i.ipv4) and _lan_rank(i.ipv4) is not None
    ]
    for interface in candidates:
        if interface.ipv4 == preferred:
            return interface
    if not candidates:
        return None
    return min(candidates, key=lambda i: _lan_rank(i.ipv4))


def list_interfaces() -> list[NetInterface]:
    stats = psutil.net_if_stats()
    found = []
    for name, addresses in psutil.net_if_addrs().items():
        up = bool(stats.get(name) and stats[name].isup)
        for address in addresses:
            if address.family.name == "AF_INET":
                found.append(NetInterface(name, address.address, up))
    return found


def lan_address() -> tuple[str, str | None]:
    """IP para o QR e o nome da placa. Sem placa da rede local, usa a rota padrao (como antes)."""
    route = local_ipv4()
    try:
        chosen = choose_lan(list_interfaces(), preferred=route)
    except OSError:
        chosen = None
    if chosen is None:
        return route, None
    return chosen.ipv4, chosen.name


def parse_profiles(text: str) -> dict[str, str]:
    """Saida de `Get-NetConnectionProfile | ConvertTo-Json` -> {placa: public|private|domain}."""
    try:
        data = json.loads(text) if text.strip() else []
    except ValueError:
        return {}
    items = data if isinstance(data, list) else [data]
    profiles = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("InterfaceAlias"), str):
            continue
        category = item.get("NetworkCategory")
        if isinstance(category, int) and category in CATEGORIES:
            profiles[item["InterfaceAlias"]] = CATEGORIES[category]
        elif isinstance(category, str):  # "Public", "Private" (ex.: com -EnumsAsStrings)
            for name in CATEGORIES.values():
                if category.lower().startswith(name):  # "DomainAuthenticated" -> domain
                    profiles[item["InterfaceAlias"]] = name
    return profiles


def read_profiles() -> dict[str, str]:
    """{placa: public|private|domain} lido do Windows; vazio fora dele ou se algo falhar."""
    if not IS_WINDOWS:
        return {}
    command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", PROFILE_SCRIPT]
    try:
        output = subprocess.run(
            command,
            capture_output=True,
            stdin=subprocess.DEVNULL,  # o .exe nao tem console: sem isso o PowerShell pode esperar
            encoding="utf-8",
            errors="replace",
            timeout=PROFILE_TIMEOUT_S,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        logger.debug("Não consegui ler o tipo de rede", exc_info=True)
        return {}
    return parse_profiles(output or "")


def network_category(interface: str | None) -> str | None:
    """Tipo da rede da placa no Windows (public, private, domain), ou None se nao souber."""
    if interface is None:
        return None
    return read_profiles().get(interface)
