"""Parsers das leituras do Windows com saidas gravadas, e as leituras reais no Windows."""

import json
import sys
import time

import pytest

from pcx_agent.diagnostics import windows as win

windows = pytest.mark.skipif(sys.platform != "win32", reason="so no Windows")

RULE = {
    "Name": "PcX Control - agente",
    "Enabled": "True",
    "Direction": "Inbound",
    "Action": "Allow",
    "Profile": "Private",
    "Program": r"C:\Program Files\PcX Control\PcXControl.exe",
}


def test_firewall_single_rule_as_object():
    (rule,) = win.parse_firewall_rules(json.dumps(RULE))
    assert (rule.enabled, rule.direction, rule.action) == (True, "in", "allow")
    assert rule.profiles == {"private"}
    assert rule.program.endswith("PcXControl.exe")


def test_firewall_list_with_bom_and_combined_profiles():
    other = {**RULE, "Enabled": "False", "Profile": "Domain, Private", "Program": "Any"}
    rules = win.parse_firewall_rules("\ufeff" + json.dumps([RULE, other]))
    assert [r.enabled for r in rules] == [True, False]
    assert rules[1].profiles == {"domain", "private"}


def test_firewall_no_rule_is_empty_list_not_unknown():
    assert win.parse_firewall_rules("") == []
    assert win.parse_firewall_rules("[]") == []
    assert win.parse_firewall_rules("null") == []


def test_firewall_garbage_or_failed_read_is_unknown():
    assert win.parse_firewall_rules("Get-NetFirewallRule : acesso negado") is None
    assert win.parse_firewall_rules(None) is None


def test_firewall_items_without_name_are_skipped():
    assert win.parse_firewall_rules(json.dumps([{"Enabled": "True"}, 3, RULE]))[0].name == RULE["Name"]


DEFENDER_ON = 397568  # 0x061100: ligado e atualizado
AVAST_ON = 266240  # 0x041000
AVAST_OFF = 262144  # 0x040000


def test_security_products():
    raw = json.dumps(
        [
            {"Kind": "AntiVirusProduct", "Name": "Windows Defender", "State": DEFENDER_ON},
            {"Kind": "AntiVirusProduct", "Name": "Avast Antivirus", "State": AVAST_ON},
            {"Kind": "FirewallProduct", "Name": "Avast Firewall", "State": AVAST_OFF},
        ]
    )
    products = win.parse_security_products(raw)
    assert [(p.name, p.kind, p.enabled, p.from_windows) for p in products] == [
        ("Windows Defender", "antivirus", True, True),
        ("Avast Antivirus", "antivirus", True, False),
        ("Avast Firewall", "firewall", False, False),
    ]


def test_security_unreadable_state_counts_as_enabled():
    (product,) = win.parse_security_products(json.dumps({"Kind": "AntiVirusProduct", "Name": "Kaspersky"}))
    assert product.enabled is True


def test_security_garbage_is_unknown_and_empty_is_none_found():
    assert win.parse_security_products("erro") is None
    assert win.parse_security_products(None) is None
    assert win.parse_security_products("[]") == []


def test_outside_windows_reads_are_unknown(monkeypatch):
    monkeypatch.setattr(win.sys, "platform", "linux")
    assert win.run_powershell("Write-Output 1") is None
    assert win.read_firewall_rules() is None


@windows
def test_real_firewall_and_security_reads_finish_in_time():
    started = time.monotonic()
    rules = win.read_firewall_rules()
    products = win.read_security_products()
    assert time.monotonic() - started < 2 * win.TIMEOUT_S + 5
    assert rules is not None  # no runner nao ha a regra: lista vazia, nao "nao deu para ler"
    assert products is None or isinstance(products, list)  # Windows Server nao tem Central de Seguranca
