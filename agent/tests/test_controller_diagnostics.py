"""Diagnostico pelo controlador da bandeja: rodar, relatorio e correcoes."""

import json
from datetime import UTC, datetime

import pytest

from pcx_agent.api.app import build_context
from pcx_agent.config import load_settings
from pcx_agent.controller import AgentController
from pcx_agent.diagnostics import fixes
from pcx_agent.diagnostics.model import AgentProbe
from pcx_agent.diagnostics.runner import ALL_CHECKS, Sources
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


def test_wait_for_rule_until_netsh_creates_it(monkeypatch):
    from pcx_agent.diagnostics import windows as win
    from pcx_agent.diagnostics.model import FirewallRule

    rule = FirewallRule("PcX Control - agente", True, "in", "allow", frozenset({"private"}), "x")
    answers = iter([[], None, [rule]])
    monkeypatch.setattr(win, "read_firewall_rules", lambda: next(answers))
    assert fixes.wait_for_rule(timeout_s=5, interval_s=0.01) is True


def test_wait_for_rule_gives_up(monkeypatch):
    from pcx_agent.diagnostics import windows as win

    monkeypatch.setattr(win, "read_firewall_rules", list)
    assert fixes.wait_for_rule(timeout_s=0.05, interval_s=0.01) is False


class _FakeServer:
    def __init__(self, port=8765, start_error=None, running=True):
        self.port = port
        self.start_error = start_error
        self.running = running
        self.restarts = []

    def restart(self, port=None):
        self.restarts.append(port)
        if port is not None:
            self.port = port


@pytest.fixture
def with_server(tmp_path):
    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())

    def build(server):
        return AgentController(ctx, 8765, server=server), ctx

    yield build
    ctx.db.close()


def test_trocar_porta_restarts_on_new_port_and_sets_message(with_server, monkeypatch):
    from pcx_agent.tray import texts

    server = _FakeServer(8765)
    controller, ctx = with_server(server)
    monkeypatch.setattr(fixes, "find_free_port", lambda start: start + 1 if start == 8766 else None)
    assert controller.apply_fix("trocar_porta") is True
    assert server.restarts == [8767]
    assert controller.port == 8767
    assert controller.last_fix_message == texts.DIAG_PORT_CHANGED.format(porta=8767)
    assert json.loads(ctx.settings.config_path.read_text(encoding="utf-8"))["port"] == 8767


def test_trocar_porta_keeps_old_port_when_save_fails(with_server, monkeypatch):
    server = _FakeServer(8765)
    controller, _ = with_server(server)
    monkeypatch.setattr(fixes, "find_free_port", lambda start: start)
    monkeypatch.setattr("pcx_agent.controller.save_port", lambda path, port: False)
    assert controller.apply_fix("trocar_porta") is False
    assert server.restarts == []
    assert controller.port == 8765
    assert controller.last_fix_message is None


def test_trocar_porta_without_free_port_fails(with_server, monkeypatch):
    server = _FakeServer(8765)
    controller, _ = with_server(server)
    monkeypatch.setattr(fixes, "find_free_port", lambda start: None)
    assert controller.apply_fix("trocar_porta") is False
    assert server.restarts == []


def test_reiniciar_servidor_keeps_the_port(with_server):
    server = _FakeServer(8765)
    controller, _ = with_server(server)
    assert controller.apply_fix("reiniciar_servidor") is True
    assert server.restarts == [None]


def test_reiniciar_sensores_calls_reset_on_the_provider(with_server):
    controller, ctx = with_server(None)
    calls = []
    ctx.provider.reset_sensors = lambda: calls.append(1)
    assert controller.apply_fix("reiniciar_sensores") is True
    assert calls == [1]


def test_reiniciar_sensores_without_reset_is_harmless(with_server):
    controller, ctx = with_server(None)
    ctx.provider = object()
    assert controller.apply_fix("reiniciar_sensores") is True


def test_program_path_is_the_running_executable():
    import sys

    assert AgentController.program_path(None) == sys.executable


def test_real_sources_report_the_server_state(with_server):
    server = _FakeServer(8765, start_error="port_in_use", running=False)
    controller, _ = with_server(server)
    assert controller._real_sources().server_state() == ("port_in_use", False)
    without, _ = with_server(None)
    assert without._real_sources().server_state() == (None, True)


def test_sensors_stopped_while_the_agent_is_off_the_network(make):
    controller, _ = make(
        reading=lambda: (None, "ainda sem leitura"),
        server_state=lambda: ("port_in_use", False),
    )
    reading = next(r for r in controller.run_diagnostics() if r.id == "sensores.leitura")
    assert reading.status == "info"
    assert reading.detail == "Sensores parados enquanto o agente não está na rede."
    assert reading.fix is None


def test_clear_crash_notice_hides_check(tmp_path):
    from pcx_agent.crashlog import PreviousSession

    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())
    try:
        previous = PreviousSession(True, datetime(2026, 11, 4, 22, 5, tzinfo=UTC))
        controller = AgentController(ctx, 8765, previous_session=previous)
        sources = controller._real_sources()
        assert sources.previous_session() is previous
        controller.clear_crash_notice()
        assert controller._real_sources().previous_session() is None
        from pcx_agent.diagnostics.runner import run_all

        ids = {r.id for r in run_all(controller._real_sources(), only={"agente.encerramento"})}
        assert ids == set()
    finally:
        ctx.db.close()


def test_run_all_includes_the_shutdown_check(make):
    from pcx_agent.crashlog import PreviousSession

    previous = PreviousSession(True, datetime(2026, 11, 4, 22, 5, tzinfo=UTC))
    controller, _ = make(previous_session=lambda: previous)
    results = controller.run_diagnostics()
    assert "agente.encerramento" in {r.id for r in results}


def test_run_checks_filters_by_id(make):
    controller, _ = make()
    assert {r.id for r in controller.run_checks({"rede.ip"})} == {"rede.ip"}
    assert len({r.id for r in controller.run_checks(None)}) > 3


def test_run_diagnostics_reports_full_results_to_hook(make):
    controller, _ = make()
    seen = []
    controller.on_results = lambda results, ran: seen.append((results, ran))
    results = controller.run_diagnostics()
    assert seen and seen[0][0] == results
    assert seen[0][1] == set(ALL_CHECKS)


def test_watch_sensor_failures_sets_sampler_hook(make):
    controller, _ = make()
    callback = lambda: None
    controller.watch_sensor_failures(callback)
    assert controller._ctx.sampler.on_sensor_failure is callback


def test_real_sources_read_gpu_failed_from_the_provider(tmp_path):
    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())
    try:
        sources = AgentController(ctx, 8765)._real_sources()
        assert sources.gpu_failed() is False  # provider sem o atributo
        ctx.provider.gpu_failed = True
        assert sources.gpu_failed() is True
    finally:
        ctx.db.close()
