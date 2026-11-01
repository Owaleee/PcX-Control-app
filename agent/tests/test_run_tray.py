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
