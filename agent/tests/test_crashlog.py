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


def test_normal_exit_is_marked_after_the_header(tmp_path):
    crashlog.install_crash_logging(tmp_path)
    crashlog.uninstall_crash_logging()
    lines = (tmp_path / crashlog.CRASH_FILE).read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("=== PcX Control ")
    assert lines[-1] == crashlog.ENDED_NORMALLY


def test_process_exit_marks_normal_exit(tmp_path):
    code = (
        "from pathlib import Path\n"
        "from pcx_agent import crashlog\n"
        f"crashlog.install_crash_logging(Path({str(tmp_path)!r}))\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=60)
    content = (tmp_path / crashlog.CRASH_FILE).read_text(encoding="utf-8")
    assert content.rstrip().endswith(crashlog.ENDED_NORMALLY)


# Arquivo por travamento, sessao anterior e manutencao.


def _now(second=0):
    from datetime import UTC, datetime

    return datetime(2026, 11, 4, 10, 30, second, tzinfo=UTC)


def test_exception_file_written_redacted_and_rotated(tmp_path):
    secret = "A" * 30
    first = crashlog.write_exception_file(tmp_path, "pcx-coletor", f"Traceback\nboom token={secret}\n", _now(0))
    assert first.name == "crash-20261104-103000.log"
    text = first.read_text(encoding="utf-8")
    assert "pcx-coletor" in text and "boom" in text and secret not in text
    for second in range(1, 12):
        crashlog.write_exception_file(tmp_path, "t", "x\n", _now(second))
    files = sorted(p.name for p in tmp_path.glob("crash-*.log"))
    assert len(files) == crashlog.MAX_CRASH_FILES == 10
    assert "crash-20261104-103000.log" not in files  # os mais antigos saem
    assert files[-1] == "crash-20261104-103011.log"


def test_same_second_gets_suffix(tmp_path):
    a = crashlog.write_exception_file(tmp_path, "t", "1\n", _now())
    b = crashlog.write_exception_file(tmp_path, "t", "2\n", _now())
    c = crashlog.write_exception_file(tmp_path, "t", "3\n", _now())
    assert [a.name, b.name, c.name] == [
        "crash-20261104-103000.log",
        "crash-20261104-103000-2.log",
        "crash-20261104-103000-3.log",
    ]


def test_hooks_write_an_exception_file(installed):
    try:
        raise RuntimeError("falha geral")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    (path,) = installed.glob("crash-*.log")
    text = path.read_text(encoding="utf-8")
    assert "MainThread" in text and "falha geral" in text


def _session(tmp_path, crash_text, last_ts):
    import json

    (tmp_path / crashlog.CRASH_FILE).write_text(crash_text, encoding="utf-8")
    lines = [json.dumps({"ts": "2026-11-04T08:00:00.000Z", "msg": "a"})]
    if last_ts is not None:
        lines.append(json.dumps({"ts": last_ts, "msg": "b"}))
    (tmp_path / "agent.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


HEADER = "=== PcX Control 0.6.0 iniciado em 2026-11-04T08:00:00Z ===\n"
BOOT = _now().timestamp() - 3600  # boot as 09:30Z


def test_previous_session_crashed_after_boot(tmp_path):
    from datetime import UTC, datetime

    _session(tmp_path, HEADER, "2026-11-04T10:15:30.250Z")
    prev = crashlog.previous_session(tmp_path, BOOT)
    assert prev.crashed is True
    assert prev.last_seen == datetime(2026, 11, 4, 10, 15, 30, 250000, tzinfo=UTC)


def test_previous_session_before_boot_is_shutdown(tmp_path):
    _session(tmp_path, HEADER, "2026-11-04T09:00:00.000Z")
    assert crashlog.previous_session(tmp_path, BOOT).crashed is False


def test_previous_session_ended_normally(tmp_path):
    _session(tmp_path, HEADER + crashlog.ENDED_NORMALLY + "\n", "2026-11-04T10:15:30.000Z")
    assert crashlog.previous_session(tmp_path, BOOT).crashed is False


def test_previous_session_only_looks_at_the_last_header(tmp_path):
    text = HEADER + "Windows fatal exception\n" + crashlog.ENDED_NORMALLY + "\n" + HEADER
    _session(tmp_path, text, "2026-11-04T10:15:30.000Z")
    assert crashlog.previous_session(tmp_path, BOOT).crashed is True


def test_previous_session_empty_or_old_format(tmp_path):
    assert crashlog.previous_session(tmp_path, BOOT).crashed is False  # sem arquivos
    _session(tmp_path, "", "2026-11-04T10:15:30.000Z")
    assert crashlog.previous_session(tmp_path, BOOT).crashed is False
    _session(tmp_path, "Fatal Python error: algo\n", "2026-11-04T10:15:30.000Z")
    assert crashlog.previous_session(tmp_path, BOOT).crashed is False
    _session(tmp_path, HEADER, None)
    (tmp_path / "agent.log").write_text("lixo que nao e json\n", encoding="utf-8")
    assert crashlog.previous_session(tmp_path, BOOT).crashed is False


def test_maintenance_trims_while_running(installed):
    path = installed / crashlog.CRASH_FILE
    with path.open("a", encoding="utf-8") as extra:
        extra.write("velho\n" * 300_000 + "ultima antiga\n")
    assert path.stat().st_size > crashlog.MAX_CRASH_BYTES
    crashlog.maintenance(installed)
    assert path.stat().st_size <= crashlog.MAX_CRASH_BYTES
    assert path.read_text(encoding="utf-8").endswith("ultima antiga\n")
    assert faulthandler.is_enabled()
    handle = crashlog._state["handle"]
    assert not handle.closed
    handle.write("depois\n")
    handle.flush()
    assert path.read_text(encoding="utf-8").endswith("depois\n")
