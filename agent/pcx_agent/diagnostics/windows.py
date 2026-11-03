"""Leituras do Windows para o diagnostico, pelo PowerShell.

Os scripts e os parsers sao separados: os parsers sao puros e testados com saidas gravadas. Uma
leitura que falha devolve None (a verificacao vira "nao deu para verificar"), nunca trava a janela.
"""

import json
import logging
import subprocess
import sys

from pcx_agent.diagnostics.model import FirewallRule, SecurityProduct

logger = logging.getLogger("pcx_agent.diagnostics")
TIMEOUT_S = 15.0
_UTF8 = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "

FIREWALL_SCRIPT = _UTF8 + (
    "$r = @(Get-NetFirewallRule -DisplayName 'PcX Control - agente' -ErrorAction SilentlyContinue | "
    "ForEach-Object { [pscustomobject]@{ Name=$_.DisplayName; Enabled=[string]$_.Enabled; "
    "Direction=[string]$_.Direction; Action=[string]$_.Action; Profile=[string]$_.Profile; "
    "Program=($_ | Get-NetFirewallApplicationFilter).Program } }); "
    "ConvertTo-Json -InputObject $r"
)
SECURITY_SCRIPT = _UTF8 + (
    "$p = @(); foreach ($k in 'AntiVirusProduct','FirewallProduct') { "
    "$p += @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName $k -ErrorAction Stop | "
    "ForEach-Object { [pscustomobject]@{ Kind=$k; Name=$_.displayName; State=[int64]$_.productState } }) }; "
    "ConvertTo-Json -InputObject $p"
)
_WINDOWS_PRODUCTS = ("windows defender", "microsoft defender", "firewall do windows", "windows firewall")


def run_powershell(script: str) -> str | None:
    """Saida do script, ou None fora do Windows, com erro ou no prazo esgotado."""
    if sys.platform != "win32":
        return None
    command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            encoding="utf-8-sig",
            errors="replace",
            timeout=TIMEOUT_S,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("PowerShell falhou no diagnostico: %s", exc)
        return None
    if completed.returncode != 0:
        logger.warning("PowerShell terminou com erro %s: %s", completed.returncode, completed.stderr.strip()[:300])
        return None
    return completed.stdout or ""


def _items(text: str | None) -> list | None:
    if text is None:
        return None
    text = text.lstrip("﻿").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


def _profiles(value: str) -> frozenset[str]:
    """'Private', 'Domain, Private' ou 'Any' (o PowerShell junta as flags com virgula)."""
    return frozenset(p.strip().lower() for p in value.split(",") if p.strip())


def parse_firewall_rules(text: str | None) -> list[FirewallRule] | None:
    items = _items(text)
    if items is None:
        return None
    rules = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("Name"), str):
            continue
        direction = str(item.get("Direction", "")).lower()
        program = item.get("Program")
        rules.append(
            FirewallRule(
                name=item["Name"],
                enabled=str(item.get("Enabled", "")).lower() == "true",
                direction="in" if direction.startswith("in") else "out" if direction.startswith("out") else direction,
                action=str(item.get("Action", "")).lower(),
                profiles=_profiles(str(item.get("Profile", ""))),
                program=program if isinstance(program, str) and program.strip() else None,
            )
        )
    return rules


def _enabled(state: object) -> bool:
    """productState da Central de Seguranca: o segundo byte 0x10 (ou 0x11) e "ligado"."""
    if not isinstance(state, int) or isinstance(state, bool):
        return True  # sem estado legivel: melhor avisar do que esconder
    return (state >> 8) & 0xFF in (0x10, 0x11)


def parse_security_products(text: str | None) -> list[SecurityProduct] | None:
    items = _items(text)
    if items is None:
        return None
    products = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("Name"), str) or not item["Name"].strip():
            continue
        name = item["Name"].strip()
        kind = "firewall" if str(item.get("Kind", "")).lower().startswith("firewall") else "antivirus"
        products.append(
            SecurityProduct(
                name=name,
                kind=kind,
                enabled=_enabled(item.get("State")),
                from_windows=any(word in name.lower() for word in _WINDOWS_PRODUCTS),
            )
        )
    return products


def read_firewall_rules() -> list[FirewallRule] | None:
    return parse_firewall_rules(run_powershell(FIREWALL_SCRIPT))


def read_security_products() -> list[SecurityProduct] | None:
    return parse_security_products(run_powershell(SECURITY_SCRIPT))
