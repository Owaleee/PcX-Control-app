"""run_tray: um erro inesperado na inicializacao vai para o log e vira mensagem, sem traceback cru."""

import argparse
import json
import logging

import pytest

import pcx_agent.main as cli


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    handlers = root.handlers[:]
    yield
    for handler in root.handlers[:]:
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()


def _args(tmp_path):
    return argparse.Namespace(data_dir=tmp_path, port=0, host="127.0.0.1")


def test_unexpected_startup_error_is_logged_and_shown(tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr("pcx_agent.winsys.dialogs.show_message",
                        lambda title, text, error=False: shown.append((text, error)))

    def broken(demo):
        raise RuntimeError("banco corrompido")

    monkeypatch.setattr(cli, "_provider", broken)
    assert cli.run_tray(_args(tmp_path)) == 1
    for handler in logging.getLogger().handlers:
        handler.flush()
    lines = (tmp_path / "logs" / "agent.log").read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert record["level"] == "ERROR"
    assert "banco corrompido" in record["exc"]
    assert shown and shown[0][1] is True
    assert "agent.log" in shown[0][0] or "logs" in shown[0][0]


def test_lock_is_released_after_startup_error(tmp_path, monkeypatch):
    monkeypatch.setattr("pcx_agent.winsys.dialogs.show_message", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_provider", lambda demo: (_ for _ in ()).throw(OSError("x")))
    cli.run_tray(_args(tmp_path))
    from pcx_agent.winsys.instance import acquire_single_instance

    lock = acquire_single_instance(tmp_path)
    assert lock is not None
    lock.release()


def test_run_tray_continues_when_port_in_use(tmp_path, monkeypatch):
    import socket
    import sys
    import types

    shown = []
    monkeypatch.setattr("pcx_agent.winsys.dialogs.show_message",
                        lambda title, text, error=False: shown.append(text))
    received = {}

    class FakeTray:
        def __init__(self, settings, server, controller, autostart):
            received["server"] = server

        def run(self):
            return 0

    monkeypatch.setitem(sys.modules, "pcx_agent.tray.app", types.SimpleNamespace(TrayApp=FakeTray))
    monkeypatch.setattr(cli, "_provider", lambda demo: __import__("pcx_agent.sensors.fake", fromlist=["x"]).FakeSensorProvider())
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        args = argparse.Namespace(data_dir=tmp_path, port=busy.getsockname()[1], host="127.0.0.1")
        assert cli.run_tray(args) == 0
    assert received["server"].start_error == "port_in_use"
    assert not received["server"].running
    assert shown == []


def test_second_instance_leaves_the_logs_of_the_first_untouched(tmp_path, monkeypatch):
    """A segunda execucao ("ja esta rodando") nao escreve no crash.log nem no agent.log: uma
    queda posterior da primeira continua sendo detectada."""
    from pcx_agent.winsys.instance import acquire_single_instance

    shown = []
    monkeypatch.setattr("pcx_agent.winsys.dialogs.show_message",
                        lambda title, text, error=False: shown.append(text))
    logs = tmp_path / "logs"
    logs.mkdir()
    crash = logs / "crash.log"
    crash.write_text("=== PcX Control 0.6.0 iniciado em 2026-11-04T10:00:00Z ===\n", encoding="utf-8")
    agent_log = logs / "agent.log"
    agent_log.write_text('{"ts": "2026-11-04T10:00:01+00:00", "msg": "rodando"}\n', encoding="utf-8")
    before = (crash.read_bytes(), agent_log.read_bytes())

    first = acquire_single_instance(tmp_path)
    assert first is not None
    try:
        assert cli.run_tray(_args(tmp_path)) == 0
    finally:
        first.release()
    assert shown  # avisou "ja esta rodando"
    assert (crash.read_bytes(), agent_log.read_bytes()) == before
