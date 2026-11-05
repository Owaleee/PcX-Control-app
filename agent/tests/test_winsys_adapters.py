"""Placa de rede pelo tipo: conversao das placas gravadas e a leitura real no Windows."""

import json
import sys
from pathlib import Path

import pytest

from pcx_agent.network import NetInterface, choose_lan, is_virtual
from pcx_agent.winsys import adapters

windows = pytest.mark.skipif(sys.platform != "win32", reason="so no Windows")
DATA = Path(__file__).parent / "data"


def load(name: str) -> list[NetInterface]:
    return adapters.interfaces_from_records(json.loads((DATA / f"{name}.json").read_text("utf-8")))


def test_classify_if_type():
    assert adapters.classify_if_type(6) == "ethernet"
    assert adapters.classify_if_type(71) == "wifi"
    assert adapters.classify_if_type(131) == "outra"
    assert adapters.classify_if_type(24) == "outra"


def test_records_become_interfaces():
    radmin, eth = load("adapters_radmin_renamed")
    assert radmin == NetInterface(
        "Ethernet 3", "26.217.199.108", True, "Famatech Radmin VPN Ethernet Adapter", "ethernet", False
    )
    assert eth.has_gateway and eth.kind == "ethernet"


def test_records_without_ipv4_are_skipped_and_oper_status_decides_up():
    records = [
        {"name": "A", "description": "", "if_type": 6, "oper_status": 1, "ipv4": None, "has_gateway": False},
        {"name": "B", "description": "", "if_type": 71, "oper_status": 2, "ipv4": "10.0.0.2", "has_gateway": False},
    ]
    (only,) = adapters.interfaces_from_records(records)
    assert only.name == "B" and only.up is False and only.kind == "wifi"


def test_renamed_radmin_is_ignored_by_description():
    interfaces = load("adapters_radmin_renamed")
    assert is_virtual("Ethernet 3", "10.200.0.1", "Famatech Radmin VPN Ethernet Adapter")
    # nem o nome nem o IP entregam; so a descricao
    renamed = NetInterface("Ethernet 3", "192.168.99.9", True, "Famatech Radmin VPN Ethernet Adapter", "ethernet")
    assert choose_lan([renamed, interfaces[1]], preferred="192.168.99.9") == interfaces[1]
    assert choose_lan(interfaces, preferred="26.217.199.108") == interfaces[1]


def test_hyperv_and_wsl_ignored():
    wsl, hyperv, wifi = load("adapters_hyperv_wsl")
    assert choose_lan([wsl, hyperv, wifi], preferred="172.25.160.1") == wifi


def test_gateway_beats_route_hint():
    eth, wifi = load("adapters_gateway_vs_route")
    assert choose_lan([eth, wifi], preferred="10.0.0.15") == eth


def test_tunnel_kind_excluded():
    tunnel, eth, wifi_off = load("adapters_tunnel")
    assert choose_lan([tunnel, eth, wifi_off], preferred="192.168.77.2") == eth


def test_psutil_fallback_kind_unknown_still_works():
    plain = NetInterface("Ethernet", "192.168.18.22", True)
    assert plain.kind == "desconhecido" and plain.description == "" and plain.has_gateway is False
    assert choose_lan([plain], preferred=None) == plain


def test_list_interfaces_falls_back_to_psutil_on_oserror(monkeypatch):
    from pcx_agent import network

    def boom():
        raise OSError("falhou")

    monkeypatch.setattr(network, "IS_WINDOWS", True)
    monkeypatch.setattr(adapters, "read_adapters", boom)
    found = network.list_interfaces()
    assert all(i.kind == "desconhecido" for i in found)


def test_list_interfaces_uses_adapters_on_windows(monkeypatch):
    from pcx_agent import network

    fake = [NetInterface("Ethernet", "192.168.1.2", True, "Realtek", "ethernet", True)]
    monkeypatch.setattr(network, "IS_WINDOWS", True)
    monkeypatch.setattr(adapters, "read_adapters", lambda: fake)
    assert network.list_interfaces() == fake


@windows
def test_read_adapters_real_has_one_up():
    found = adapters.read_adapters()
    assert any(i.up and i.kind in ("ethernet", "wifi") for i in found)
    assert all(i.ipv4.count(".") == 3 for i in found)


def test_vpn_check_and_report_show_driver_description():
    from pcx_agent.diagnostics.checks import check_vpn, label

    radmin, eth = load("adapters_radmin_renamed")
    assert label(radmin) == "Ethernet 3 (Famatech Radmin VPN Ethernet Adapter)"
    assert label(NetInterface("Ethernet", "192.168.1.2", True)) == "Ethernet"
    (result,) = check_vpn([radmin, eth])
    assert "Ethernet 3 (Famatech Radmin VPN Ethernet Adapter)" in result.detail
