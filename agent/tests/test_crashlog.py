"""Travamentos deixam registro: excecoes em qualquer thread, no laco do servidor e travas nativas."""

import asyncio
import faulthandler
import logging
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from pcx_agent import crashlog


@pytest.fixture
def installed(tmp_path):
    crashlog.install_crash_logging(tmp_path)
    yield tmp_path
    crashlog.uninstall_crash_logging()


def _critical(caplog):
    return [r for r in caplog.records if r.levelno == logging.CRITICAL]


def test_exception_in_a_thread_is_logged_with_the_thread_name(installed, caplog):
    def boom():
        raise RuntimeError("sensor travou")

    with caplog.at_level(logging.INFO):
        thread = threading.Thread(target=boom, name="pcx-coletor")
        thread.start()
        thread.join()
    (record,) = _critical(caplog)
    assert "pcx-coletor" in record.getMessage()
    assert record.exc_info is not None and record.exc_info[0] is RuntimeError


def test_uncaught_exception_in_the_main_thread_is_logged(installed, caplog):
    with caplog.at_level(logging.INFO):
        try:
            raise ValueError("falha geral")
        except ValueError:
            sys.excepthook(*sys.exc_info())
    (record,) = _critical(caplog)
    assert "MainThread" in record.getMessage()
    assert record.exc_info[1].args == ("falha geral",)


def test_ctrl_c_is_not_logged_as_a_crash(installed, caplog):
    with caplog.at_level(logging.INFO):
        try:
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            sys.excepthook(*sys.exc_info())
    assert _critical(caplog) == []


def test_crash_file_is_created_with_a_header_and_faulthandler_points_to_it(installed):
    content = (installed / crashlog.CRASH_FILE).read_text(encoding="utf-8")
    assert content.startswith("=== PcX Control ")
    assert faulthandler.is_enabled()


def test_big_crash_file_keeps_only_the_end(tmp_path):
    path = tmp_path / crashlog.CRASH_FILE
    path.write_text("velho\n" * 300_000 + "ultima linha antiga\n", encoding="utf-8")
    assert path.stat().st_size > crashlog.MAX_CRASH_BYTES
    crashlog.trim_crash_file(path)
    content = path.read_text(encoding="utf-8")
    assert path.stat().st_size <= crashlog.MAX_CRASH_BYTES
    assert content.endswith("ultima linha antiga\n")
    assert content.startswith("velho\n")  # corta numa quebra de linha, sem linha pela metade


def test_small_crash_file_is_untouched(tmp_path):
    path = tmp_path / crashlog.CRASH_FILE
    path.write_text("pequeno\n", encoding="utf-8")
    crashlog.trim_crash_file(path)
    assert path.read_text(encoding="utf-8") == "pequeno\n"


def test_asyncio_loop_errors_are_logged_with_traceback(caplog):
    loop = asyncio.new_event_loop()
    try:
        loop.set_exception_handler(crashlog.asyncio_exception_handler)
        with caplog.at_level(logging.ERROR):
            try:
                raise OSError("conexao caiu no meio")
            except OSError as exc:
                loop.call_exception_handler({"message": "Task exception was never retrieved", "exception": exc})
    finally:
        loop.close()
    (record,) = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert "Task exception was never retrieved" in record.getMessage()
    assert record.exc_info[0] is OSError


def test_startup_line_has_versions(installed, caplog):
    with caplog.at_level(logging.INFO):
        crashlog.log_startup()
    (line,) = [r.getMessage() for r in caplog.records if r.getMessage().startswith("PcX Control ")]
    assert "Python" in line and "sistema" in line and "executavel" in line


def test_native_crash_leaves_a_stack_in_crash_log(tmp_path):
    """Simula uma DLL de driver derrubando o processo: o crash.log precisa ter a pilha."""
    code = (
        "import faulthandler, sys\n"
        "from pathlib import Path\n"
        "from pcx_agent import crashlog\n"
        f"crashlog.install_crash_logging(Path({str(tmp_path)!r}))\n"
        "faulthandler._sigsegv()\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=60, check=False)
    assert result.returncode != 0
    content = (tmp_path / crashlog.CRASH_FILE).read_text(encoding="utf-8", errors="replace")
    assert "=== PcX Control " in content
    assert "Fatal Python error" in content


def test_uninstall_restores_the_previous_hooks(tmp_path):
    before = (sys.excepthook, threading.excepthook)
    crashlog.install_crash_logging(tmp_path)
    crashlog.uninstall_crash_logging()
    assert (sys.excepthook, threading.excepthook) == before
    assert Path(tmp_path / crashlog.CRASH_FILE).exists()


def test_server_loop_uses_the_crash_handler(tmp_path):
    from fastapi.testclient import TestClient

    from pcx_agent.api.app import build_context, create_app
    from pcx_agent.config import load_settings
    from pcx_agent.sensors.fake import FakeSensorProvider

    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider())
    try:
        with TestClient(create_app(ctx, run_sampler=False)) as client:
            handler = client.portal.call(lambda: asyncio.get_running_loop().get_exception_handler())
        assert handler is crashlog.asyncio_exception_handler
    finally:
        ctx.db.close()


def test_agent_start_installs_crash_logging(tmp_path, monkeypatch):
    from pcx_agent import main as main_module

    calls = []
    monkeypatch.setattr(main_module, "install_crash_logging", lambda folder: calls.append(Path(folder)))
    monkeypatch.setattr(main_module, "log_startup", lambda: calls.append("startup"))
    assert main_module.main(["--demo", "--dry-run", "--data-dir", str(tmp_path)]) == 0
    assert calls == [tmp_path / "logs", "startup"]
