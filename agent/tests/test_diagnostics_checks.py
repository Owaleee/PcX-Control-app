"""Cada verificacao do diagnostico em cada situacao da spec."""

from datetime import UTC, datetime

import pytest

from pcx_agent.diagnostics import checks
from pcx_agent.diagnostics.model import AgentProbe, FirewallRule, SecurityProduct
from pcx_agent.network import NetInterface
from pcx_agent.sensors.base import DiskVolume, GpuReading, Snapshot

ETH = NetInterface("Ethernet", "192.168.18.22", True)
RADMIN = NetInterface("Radmin VPN", "26.217.199.108", True)
EXE = r"C:\Program Files\PcX Control\PcXControl.exe"


def only(results):
    (result,) = results
    return result


# rede.ip


def test_ip_ok_shows_address_and_interface():
    r = only(checks.check_ip([ETH], ETH))
    assert (r.id, r.status) == ("rede.ip", "ok")
    assert "192.168.18.22" in r.detail and "Ethernet" in r.detail


def test_ip_apipa_means_router_gave_no_address():
    apipa = NetInterface("Ethernet", "169.254.10.4", True)
    r = only(checks.check_ip([apipa], None))
    assert r.status == "problema" and "169.254" in r.detail


def test_ip_only_vpn():
    r = only(checks.check_ip([RADMIN], None))
    assert r.status == "problema" and "VPN" in r.detail


def test_ip_no_network():
    r = only(checks.check_ip([], None))
    assert r.status == "problema" and "sem rede" in r.detail


# rede.tipo


@pytest.mark.parametrize(
    ("category", "status", "fix"),
    [("private", "ok", None), ("public", "problema", "abrir_rede"), ("domain", "atencao", None)],
)
def test_network_type(category, status, fix):
    r = only(checks.check_network_type(ETH, {"Ethernet": category}))
    assert (r.id, r.status, r.fix) == ("rede.tipo", status, fix)


@pytest.mark.parametrize(("chosen", "profiles"), [(ETH, None), (ETH, {}), (None, {"Ethernet": "private"})])
def test_network_type_unknown_is_info(chosen, profiles):
    assert only(checks.check_network_type(chosen, profiles)).status == "info"


# rede.firewall


def rule(**changes) -> FirewallRule:
    values = {
        "name": checks.RULE_NAME,
        "enabled": True,
        "direction": "in",
        "action": "allow",
        "profiles": frozenset({"private"}),
        "program": EXE,
    }
    values.update(changes)
    return FirewallRule(**values)


def test_firewall_ok():
    assert only(checks.check_firewall([rule()], EXE)).status == "ok"


def test_firewall_program_path_compares_without_case():
    assert only(checks.check_firewall([rule(program=EXE.lower())], EXE)).status == "ok"
    assert only(checks.check_firewall([rule(program=EXE.replace("\\", "/"))], EXE)).status == "ok"


def test_firewall_any_profile_counts():
    assert only(checks.check_firewall([rule(profiles=frozenset({"any"}))], EXE)).status == "ok"


@pytest.mark.parametrize(
    ("rules", "words"),
    [
        ([], "não existe"),
        ([rule(enabled=False)], "desativada"),
        ([rule(action="block")], "entrada"),
        ([rule(direction="out")], "entrada"),
        ([rule(profiles=frozenset({"public"}))], "Privada"),
        ([rule(program=r"C:\antigo\PcXControl.exe")], "outro programa"),
        ([rule(name="Outra regra")], "não existe"),
    ],
)
def test_firewall_problems_offer_to_create_the_rule(rules, words):
    r = only(checks.check_firewall(rules, EXE))
    assert (r.status, r.fix) == ("problema", "criar_firewall")
    assert words in r.detail


def test_firewall_one_good_rule_among_old_ones_is_ok():
    rules = [rule(program=r"C:\antigo\PcXControl.exe"), rule()]
    assert only(checks.check_firewall(rules, EXE)).status == "ok"


def test_firewall_from_source_code_is_info():
    r = only(checks.check_firewall([], None))
    assert (r.status, r.fix) == ("info", None)


def test_firewall_unreadable_is_info():
    assert only(checks.check_firewall(None, EXE)).status == "info"


# rede.vpn


def test_vpn_names_are_listed():
    tailscale = NetInterface("Tailscale", "100.101.1.2", True)
    r = only(checks.check_vpn([ETH, RADMIN, tailscale]))
    assert r.status == "atencao"
    assert "Radmin VPN" in r.detail and "Tailscale" in r.detail


def test_vpn_by_address_range_even_with_unknown_name():
    renamed = NetInterface("Ethernet 3", "26.1.2.3", True)
    assert only(checks.check_vpn([ETH, renamed])).status == "atencao"


def test_vpn_down_or_virtual_machine_adapters_are_not_vpn():
    down = NetInterface("Radmin VPN", "26.1.2.3", False)
    wsl = NetInterface("vEthernet (WSL)", "172.20.0.1", True)
    assert only(checks.check_vpn([ETH, down, wsl])).status == "ok"


# agente.local


def test_agent_ok_says_the_test_is_from_inside_the_pc():
    r = only(checks.check_agent(AgentProbe(reachable=True, same_agent=True), "192.168.18.22:8765"))
    assert r.status == "ok" and "dentro do PC" in r.detail


def test_agent_unreachable():
    r = only(checks.check_agent(AgentProbe(reachable=False, error="tempo esgotado"), "192.168.18.22:8765"))
    assert r.status == "problema" and "tempo esgotado" in r.detail


def test_other_program_on_the_port():
    r = only(checks.check_agent(AgentProbe(reachable=True, same_agent=False), "192.168.18.22:8765"))
    assert r.status == "problema" and "Outro programa" in r.detail


# antivirus.terceiros


def product(name, kind="antivirus", enabled=True, from_windows=False):
    return SecurityProduct(name, kind, enabled, from_windows)


def test_only_windows_protection_is_ok():
    r = only(checks.check_antivirus([product("Microsoft Defender Antivirus", from_windows=True)]))
    assert r.status == "ok"


def test_each_third_party_product_is_a_warning():
    results = checks.check_antivirus(
        [product("Avast Antivirus"), product("ESET Firewall", "firewall"), product("Microsoft Defender Antivirus", from_windows=True)]
    )
    assert [(r.title, r.status) for r in results] == [("Avast Antivirus", "atencao"), ("ESET Firewall", "atencao")]
    assert "libere o PcX Control" in results[0].detail
    assert results[1].detail.startswith("Firewall")


def test_disabled_third_party_product_is_ignored():
    assert only(checks.check_antivirus([product("Avast Antivirus", enabled=False)])).status == "ok"


def test_antivirus_unreadable_is_info():
    assert only(checks.check_antivirus(None)).status == "info"


# sensores


def gpu(name, vendor, vram_gib, temp=None):
    return GpuReading(
        id=f"luid_{name}", name=name, usage_percent=1.0, vram_total_bytes=vram_gib * 1024**3, temp_c=temp, vendor=vendor
    )


def test_each_card_is_listed_with_vendor_vram_and_temperature():
    results = checks.check_gpus([gpu("AMD Radeon RX 7600", "amd", 8, 52.0), gpu("Intel UHD", "intel", 1)])
    assert [r.title for r in results] == ["AMD Radeon RX 7600", "Intel UHD"]
    assert all(r.status == "info" for r in results)
    assert "AMD" in results[0].detail and "8.0 GiB" in results[0].detail
    assert "temperatura disponível" in results[0].detail and "mostrada no app" in results[0].detail
    assert "sem temperatura" in results[1].detail and "mostrada no app" not in results[1].detail


def test_no_card_is_a_warning():
    assert only(checks.check_gpus([])).status == "atencao"


def test_reading_ok_and_failed():
    snapshot = Snapshot(
        t=datetime.now(UTC), cpu_total=1, ram_percent=1, ram_used_bytes=1, ram_total_bytes=2,
        disks=[DiskVolume(mount="C:\\", percent=1, used_bytes=1, total_bytes=2)],
        disk_read_bps=0, disk_write_bps=0, net_down_bps=0, net_up_bps=0, gpus=[], host_name="PC", uptime_s=1,
    )
    assert only(checks.check_reading(snapshot, None)).status == "ok"
    failed = only(checks.check_reading(None, "OSError: PDH"))
    assert failed.status == "problema" and "OSError: PDH" in failed.detail
