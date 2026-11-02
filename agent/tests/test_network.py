"""Escolha do IP do QR: a placa da rede local, nunca VPNs ou placas virtuais."""

import pytest

from pcx_agent.network import NetInterface, choose_lan, is_virtual, lan_address, parse_profiles

ETH = NetInterface("Ethernet", "192.168.18.22", True)
RADMIN = NetInterface("Radmin VPN", "26.217.199.108", True)


def test_ethernet_wins_over_radmin_even_when_route_goes_through_vpn():
    assert choose_lan([RADMIN, ETH], preferred="26.217.199.108") == ETH


@pytest.mark.parametrize(
    ("name", "ip"),
    [
        ("Radmin VPN", "26.1.2.3"),
        ("Hamachi", "25.4.5.6"),
        ("Tailscale", "100.101.102.103"),
        ("ZeroTier One [abc]", "10.147.17.5"),
        ("vEthernet (WSL)", "172.25.160.1"),
        ("VirtualBox Host-Only Network", "192.168.56.1"),
        ("VMware Network Adapter VMnet8", "192.168.40.1"),
        ("OpenVPN TAP-Windows6", "10.8.0.6"),
        ("WireGuard Tunnel", "10.66.66.2"),
        ("Conexão de Rede Bluetooth", "192.168.44.1"),
        ("Wi-Fi", "169.254.10.20"),
        ("Loopback Pseudo-Interface 1", "127.0.0.1"),
    ],
)
def test_virtual_and_vpn_adapters_are_ignored(name, ip):
    assert is_virtual(name, ip)
    assert choose_lan([NetInterface(name, ip, True), ETH], preferred=ip) == ETH


def test_real_adapters_are_not_virtual():
    assert not is_virtual("Ethernet", "192.168.18.22")
    assert not is_virtual("Wi-Fi", "10.0.0.15")


def test_disconnected_adapter_is_ignored():
    wifi_off = NetInterface("Wi-Fi", "192.168.0.50", False)
    assert choose_lan([wifi_off, ETH], preferred=None) == ETH


def test_route_adapter_wins_among_real_ones():
    wifi = NetInterface("Wi-Fi", "10.0.0.15", True)
    assert choose_lan([ETH, wifi], preferred="10.0.0.15") == wifi


def test_without_route_hint_prefers_192_168_then_10_then_172():
    a = NetInterface("A", "172.16.0.2", True)
    b = NetInterface("B", "10.0.0.2", True)
    c = NetInterface("C", "192.168.1.2", True)
    assert choose_lan([a, b, c], preferred=None) == c
    assert choose_lan([a, b], preferred=None) == b


def test_public_ip_is_not_a_lan_candidate():
    assert choose_lan([NetInterface("Ethernet", "200.150.1.2", True)], preferred=None) is None


def test_only_vpn_returns_none():
    assert choose_lan([RADMIN], preferred="26.217.199.108") is None


def test_lan_address_falls_back_to_route_ip(monkeypatch):
    from pcx_agent import network

    monkeypatch.setattr(network, "list_interfaces", lambda: [RADMIN])
    monkeypatch.setattr(network, "local_ipv4", lambda: "26.217.199.108")
    assert lan_address() == ("26.217.199.108", None)


def test_lan_address_uses_real_adapter(monkeypatch):
    from pcx_agent import network

    monkeypatch.setattr(network, "list_interfaces", lambda: [RADMIN, ETH])
    monkeypatch.setattr(network, "local_ipv4", lambda: "26.217.199.108")
    assert lan_address() == ("192.168.18.22", "Ethernet")


def test_list_interfaces_reads_this_machine():
    from pcx_agent.network import list_interfaces

    found = list_interfaces()
    assert all(isinstance(i, NetInterface) for i in found)
    assert all(i.ipv4.count(".") == 3 for i in found)


# --- tipo de rede do Windows (Get-NetConnectionProfile | ConvertTo-Json) -----------------


def test_parse_profiles_list_with_numbers_powershell_5():
    text = '[{"InterfaceAlias":"Ethernet","NetworkCategory":0},{"InterfaceAlias":"Radmin VPN","NetworkCategory":1}]'
    assert parse_profiles(text) == {"Ethernet": "public", "Radmin VPN": "private"}


def test_parse_profiles_single_object_with_text_powershell_7():
    text = '{"InterfaceAlias":"Wi-Fi","NetworkCategory":"Private"}'
    assert parse_profiles(text) == {"Wi-Fi": "private"}


def test_parse_profiles_domain_and_garbage():
    assert parse_profiles('{"InterfaceAlias":"Ethernet","NetworkCategory":2}') == {"Ethernet": "domain"}
    assert parse_profiles("") == {}
    assert parse_profiles("isto nao e json") == {}
    assert parse_profiles('[{"NetworkCategory":0}]') == {}


@pytest.mark.windows
@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Get-NetConnectionProfile")
def test_network_category_runs_on_windows():
    import time

    from pcx_agent.network import network_category, read_profiles

    started = time.monotonic()
    profiles = read_profiles()
    assert time.monotonic() - started < 6
    # O runner do GitHub sempre tem uma rede: vazio aqui quer dizer leitura quebrada (ex.: BOM).
    assert profiles, "Get-NetConnectionProfile nao devolveu nenhuma rede"
    assert all(value in ("public", "private", "domain") for value in profiles.values())
    name = next(iter(profiles))
    assert network_category(name) == profiles[name]


def test_read_profiles_asks_powershell_for_utf8_and_keeps_accents(monkeypatch):
    """No Windows em portugues a placa pode se chamar "Conexao Local" com til; sem UTF-8 o nome
    nao bate e o aviso de rede Publica nunca aparece."""
    import subprocess

    from pcx_agent import network

    calls = {}

    class Done:
        stdout = '[{"InterfaceAlias":"Conexão Local","NetworkCategory":0}]'

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls.update(kwargs)
        return Done()

    monkeypatch.setattr(network, "IS_WINDOWS", True)
    monkeypatch.setattr(network.subprocess, "run", fake_run)
    assert network.read_profiles() == {"Conexão Local": "public"}
    assert "[Console]::OutputEncoding" in calls["command"][-1]
    assert calls["encoding"] == "utf-8-sig"
    assert calls["stdin"] == subprocess.DEVNULL


def test_read_profiles_outside_windows_is_empty(monkeypatch):
    from pcx_agent import network

    monkeypatch.setattr(network, "IS_WINDOWS", False)
    assert network.read_profiles() == {}


def test_parse_profiles_ignores_utf8_bom():
    """Com OutputEncoding UTF-8 o PowerShell 5.1 pode escrever um BOM no inicio da saida."""
    assert parse_profiles('﻿{"InterfaceAlias":"Wi-Fi","NetworkCategory":0}') == {"Wi-Fi": "public"}


def test_read_profiles_decodes_with_bom_tolerance(monkeypatch):
    from pcx_agent import network

    seen = {}

    class Done:
        stdout = '﻿[{"InterfaceAlias":"Ethernet","NetworkCategory":1}]'

    def fake_run(command, **kwargs):
        seen.update(kwargs)
        return Done()

    monkeypatch.setattr(network, "IS_WINDOWS", True)
    monkeypatch.setattr(network.subprocess, "run", fake_run)
    assert network.read_profiles() == {"Ethernet": "private"}
    assert seen["encoding"] == "utf-8-sig"


def test_windows_mobile_hotspot_adapter_is_ignored():
    hotspot = NetInterface("Conexão Local* 10", "192.168.137.1", True)
    lan = NetInterface("Ethernet", "10.0.0.20", True)
    assert is_virtual(hotspot.name, hotspot.ipv4)
    assert choose_lan([hotspot, lan], preferred="26.1.2.3") == lan
