"""Executor do diagnostico, sonda do agente e relatorio."""

import logging
from datetime import UTC, datetime

from pcx_agent.diagnostics import runner
from pcx_agent.diagnostics.model import GROUPS, AgentProbe, FirewallRule
from pcx_agent.diagnostics.report import ReportFacts, build_report, engine_types
from pcx_agent.network import NetInterface
from pcx_agent.sensors.base import GpuReading, Snapshot

ETH = NetInterface("Ethernet", "192.168.18.22", True)
RADMIN = NetInterface("Radmin VPN", "26.217.199.108", True)
EXE = r"C:\Program Files\PcX Control\PcXControl.exe"
GPU = GpuReading(
    id="luid_0x00000000_0x00009962_phys_0", name="AMD Radeon RX 7600", usage_percent=1.9,
    vram_total_bytes=8 * 1024**3, temp_c=52.0, vendor="amd",
)
SNAPSHOT = Snapshot(
    t=datetime.now(UTC), cpu_total=10, ram_percent=50, ram_used_bytes=1, ram_total_bytes=2, disks=[],
    disk_read_bps=0, disk_write_bps=0, net_down_bps=0, net_up_bps=0, gpus=[GPU], host_name="PC", uptime_s=1,
)


def sources(**changes) -> runner.Sources:
    values = {
        "interfaces": lambda: [ETH, RADMIN],
        "route": lambda: "26.217.199.108",
        "profiles": lambda: {"Ethernet": "public", "Radmin VPN": "public"},
        "firewall_rules": lambda: [
            FirewallRule("PcX Control - agente", True, "in", "allow", frozenset({"private"}), EXE)
        ],
        "exe_path": lambda: EXE,
        "security": list,
        "probe": lambda address: AgentProbe(reachable=True, same_agent=True),
        "reading": lambda: (SNAPSHOT, None),
        "port": 8765,
    }
    values.update(changes)
    return runner.Sources(**values)


def by_id(results):
    found = {}
    for r in results:
        found.setdefault(r.id, []).append(r)
    return found


def test_friends_pc_case_points_to_the_public_network_and_the_vpn():
    """O caso real: Ethernet em rede Publica, Radmin ligada, regra existente."""
    results = by_id(runner.run_all(sources()))
    assert results["rede.ip"][0].status == "ok" and "192.168.18.22" in results["rede.ip"][0].detail
    assert (results["rede.tipo"][0].status, results["rede.tipo"][0].fix) == ("problema", "abrir_rede")
    assert results["rede.firewall"][0].status == "ok"
    assert results["rede.vpn"][0].status == "atencao"
    assert results["sensores.gpu"][0].title == "AMD Radeon RX 7600"


def test_all_eight_checks_in_group_order():
    results = runner.run_all(sources())
    assert [r.id for r in results] == [
        "rede.ip", "rede.tipo", "rede.firewall", "rede.vpn", "agente.local",
        "antivirus.terceiros", "sensores.gpu", "sensores.leitura",
    ]
    assert [GROUPS.index(r.group) for r in results] == sorted(GROUPS.index(r.group) for r in results)


def test_probe_uses_the_lan_address_and_port():
    asked = []
    runner.run_all(sources(probe=lambda address: asked.append(address) or AgentProbe(reachable=True, same_agent=True)))
    assert asked == ["192.168.18.22:8765"]


def test_a_check_that_raises_becomes_info_and_the_others_still_run(caplog):
    def broken():
        raise RuntimeError("WMI travou")

    with caplog.at_level(logging.WARNING, logger="pcx_agent.diagnostics"):
        results = by_id(runner.run_all(sources(security=broken)))
    (av,) = results["antivirus.terceiros"]
    assert av.status == "info" and "RuntimeError: WMI travou" in av.detail
    assert results["sensores.leitura"][0].status == "ok"
    assert any(r.exc_info for r in caplog.records)


def test_interfaces_failing_still_gives_every_check():
    def broken():
        raise OSError("psutil")

    results = by_id(runner.run_all(sources(interfaces=broken)))
    assert results["rede.ip"][0].status == "problema"
    assert len(results) == 8


def test_each_result_is_logged(caplog):
    with caplog.at_level(logging.INFO, logger="pcx_agent.diagnostics"):
        results = runner.run_all(sources())
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Diagnostico ")]
    assert len(lines) == len(results)
    assert "rede.tipo" in lines[1] and "problema" in lines[1]


def test_probe_agent_against_a_closed_port():
    probe = runner.probe_agent("127.0.0.1:9", "id", timeout=1.0)
    assert probe.reachable is False and probe.error


def test_exe_path_only_when_frozen(monkeypatch):
    monkeypatch.delattr(runner.sys, "frozen", raising=False)
    assert runner.exe_path() is None
    monkeypatch.setattr(runner.sys, "frozen", True, raising=False)
    assert runner.exe_path() == runner.sys.executable


# Relatorio

INSTANCES = [
    "pid_12468_luid_0x00000000_0x00009962_phys_0_eng_12_engtype_video codec 0",
    "pid_12468_luid_0x00000000_0x00009962_phys_0_eng_2_engtype_compute 0",
    "pid_999_luid_0x00000000_0x00009962_phys_0_eng_0_engtype_3D",
    "pid_1000_luid_0x00000000_0x00009962_phys_0_eng_0_engtype_3D#1",
]


def test_engine_types_per_card_without_pids():
    assert engine_types(INSTANCES) == {"LUID 0x00000000_0x00009962 phys 0": ["3D", "compute 0", "video codec 0"]}


def test_report_has_versions_results_cards_and_engines():
    results = runner.run_all(sources())
    text = build_report(
        results, ReportFacts("0.5.0", "10.0.19045", interfaces=[ETH, RADMIN], gpus=[GPU], pdh_instances=INSTANCES)
    )
    assert text.startswith("PcX Control 0.5.0 - relatório de diagnóstico\nWindows: 10.0.19045\n")
    assert "[Rede e firewall]" in text and "- PROBLEMA | Tipo de rede no Windows:" in text
    assert "- Ethernet: 192.168.18.22 | ligada | rede" in text
    assert "- Radmin VPN: 26.217.199.108 | ligada | VPN" in text
    assert "- AMD Radeon RX 7600 | AMD | 8.0 GiB | uso 2% | 52 °C" in text
    assert "Motores de LUID 0x00000000_0x00009962 phys 0: 3D, compute 0, video codec 0" in text
    assert "[oculto]" not in text


def test_report_never_carries_secrets():
    token = "Zx9-aB3_cD5eF7gH9iJ1kL3mN5"  # formato de token_urlsafe
    results = runner.run_all(sources(probe=lambda a: AgentProbe(reachable=False, error=f"pcx://pair?c=1234&t={token}")))
    text = build_report(results, ReportFacts("0.5.0", "10"))
    assert token not in text and "c=1234" not in text
