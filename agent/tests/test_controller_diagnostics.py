"""Diagnostico pelo controlador da bandeja: rodar, relatorio e correcoes."""

from datetime import UTC, datetime

import pytest

from pcx_agent.api.app import build_context
from pcx_agent.config import load_settings
from pcx_agent.controller import AgentController
from pcx_agent.diagnostics import fixes
from pcx_agent.diagnostics.model import AgentProbe
from pcx_agent.diagnostics.runner import Sources
from pcx_agent.network import NetInterface
from pcx_agent.sensors.base import GpuReading, Snapshot
from pcx_agent.sensors.fake import FakeSensorProvider

ETH = NetInterface("Ethernet", "192.168.18.22", True)
GPU = GpuReading(id="luid_x", name="AMD Radeon RX 7600", usage_percent=2, vram_total_bytes=8 * 1024**3, vendor="amd")
SNAPSHOT = Snapshot(
    t=datetime.now(UTC), cpu_total=1, ram_percent=1, ram_used_bytes=1, ram_total_bytes=2, disks=[],
    disk_read_bps=0, disk_write_bps=0, net_down_bps=0, net_up_bps=0, gpus=[GPU], host_name="PC", uptime_s=1,
)


@pytest.fixture
def make(tmp_path):
    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())
    calls = []

    def build(**sources_changes):
        values = {
            "interfaces": lambda: [ETH],
            "route": lambda: "192.168.18.22",
            "profiles": lambda: {"Ethernet": "public"},
            "firewall_rules": list,
            "exe_path": lambda: None,
            "security": list,
            "probe": lambda address: AgentProbe(reachable=True, same_agent=True),
            "reading": lambda: (SNAPSHOT, None),
            "port": 8765,
        }
        values.update(sources_changes)
        return AgentController(
            ctx,
            8765,
            diagnostics_sources=lambda: Sources(**values),
            fix_actions={
                "abrir_rede": lambda: calls.append("abrir_rede") or True,
                "criar_firewall": lambda: calls.append("criar_firewall") or False,
            },
        ), calls

    yield build
    ctx.db.close()


def test_run_diagnostics_returns_every_check(make):
    controller, _ = make()
    results = controller.run_diagnostics()
    assert len({r.id for r in results}) == 8
    assert next(r for r in results if r.id == "rede.tipo").fix == "abrir_rede"


def test_report_uses_the_agent_version_and_the_last_reading(make):
    controller, _ = make()
    text = controller.diagnostics_report(controller.run_diagnostics())
    assert text.startswith(f"PcX Control {controller._ctx.settings.version} - relatório")
    assert "AMD Radeon RX 7600 | AMD" in text
    assert "- Ethernet: 192.168.18.22 | ligada | rede" in text


def test_report_without_reading_yet(make):
    controller, _ = make(reading=lambda: (None, "ainda sem leitura"))
    text = controller.diagnostics_report(controller.run_diagnostics())
    assert "Leitura dos sensores: A leitura falhou: ainda sem leitura." in text


def test_apply_fix_calls_the_action(make):
    controller, calls = make()
    assert controller.apply_fix("abrir_rede") is True
    assert controller.apply_fix("criar_firewall") is False
    assert calls == ["abrir_rede", "criar_firewall"]


def test_real_sources_use_the_sampler_and_this_agent(tmp_path):
    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())
    try:
        controller = AgentController(ctx, 8765)
        sources = controller._real_sources()
        assert sources.port == 8765
        assert sources.reading() == (None, "ainda sem leitura")
        ctx.sampler.latest = SNAPSHOT
        assert sources.reading() == (SNAPSHOT, None)
    finally:
        ctx.db.close()


def test_firewall_command_uses_the_installer_script():
    program, params = fixes.firewall_command(r"C:\Program Files\PcX Control\PcXControl.exe")
    assert program == "cmd.exe"
    assert params == '/c ""C:\\Program Files\\PcX Control\\firewall.cmd" add "C:\\Program Files\\PcX Control\\PcXControl.exe""'


def test_fixes_do_nothing_outside_windows(monkeypatch):
    monkeypatch.setattr(fixes.sys, "platform", "linux")
    assert fixes.open_network_settings() is False
    assert fixes.create_firewall_rule(r"C:\x\PcXControl.exe") is False
    assert fixes.create_firewall_rule(None) is False
