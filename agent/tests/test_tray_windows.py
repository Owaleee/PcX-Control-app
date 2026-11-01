"""Janelas da bandeja de verdade (tkinter). Rodam na CI do Windows."""

import os
import sys
import threading
import time

import pytest

tk = pytest.importorskip("tkinter")

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(
        sys.platform != "win32" and not os.environ.get("DISPLAY"), reason="sem tela"
    ),
]


@pytest.fixture
def root():
    window = tk.Tk()
    window.withdraw()
    from pcx_agent.tray.widgets import apply_style

    apply_style(window)
    yield window
    window.destroy()


@pytest.fixture
def controller(tmp_path):
    from pcx_agent.api.app import build_context
    from pcx_agent.config import load_settings
    from pcx_agent.controller import AgentController
    from pcx_agent.sensors.fake import FakeSensorProvider

    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider(seed=2))
    yield AgentController(ctx, 8765, host_lookup=lambda: "192.168.0.15")
    ctx.db.close()


def _windows():
    from pcx_agent.tray.devices import DevicesWindow
    from pcx_agent.tray.first_run import FirstRunWindow
    from pcx_agent.tray.pairing import PairingWindow
    from pcx_agent.tray.password import PasswordWindow

    return [FirstRunWindow, PairingWindow, DevicesWindow, PasswordWindow]


def test_windows_open_and_close(root, controller):
    for cls in _windows():
        window = cls.show(root, controller)
        root.update()
        assert window.winfo_exists()
        window.close()
        root.update()


def test_show_twice_reuses_window(root, controller):
    from pcx_agent.tray.pairing import PairingWindow

    first = PairingWindow.show(root, controller)
    second = PairingWindow.show(root, controller)
    assert first is second
    first.close()


def test_first_run_shows_mismatch_error(root, controller):
    from pcx_agent.tray.first_run import FirstRunWindow

    window = FirstRunWindow.show(root, controller)
    window.password_field.set_value("senha-boa-1")
    window.confirm_field.set_value("senha-boa-2")
    window.primary_action()
    root.update()
    assert window.confirm_field.error_text() == "As senhas não são iguais."
    assert window.step == 1
    window.password_field.set_value("senha-boa-1")
    window.confirm_field.set_value("senha-boa-1")
    window.primary_action()
    root.update()
    assert window.step == 2
    assert not controller.needs_first_run()
    window.close()


def test_pairing_window_shows_paired_and_closes(root, controller):
    from pcx_agent.tray.pairing import AUTO_CLOSE_MS, PairingFrame, PairingWindow

    window = PairingWindow.show(root, controller)
    root.update()
    PairingFrame.broadcast_paired("Poco X7 Pro")
    root.update()
    assert "Poco X7 Pro" in window.frame._content.cget("text")
    deadline = time.monotonic() + AUTO_CLOSE_MS / 1000 + 2
    while window.winfo_exists() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    assert not window.winfo_exists()


def test_devices_window_lists_and_revokes(root, controller):
    from pcx_agent.tray.devices import DevicesWindow

    pairing = controller._ctx.pairing
    device = pairing.pair("Poco", code=pairing.new_code(), client_ip="10.0.0.1").device_id
    window = DevicesWindow.show(root, controller)
    root.update()
    assert window.table.get_children() == (device,)
    window.table.selection_set(device)
    window._revoke_selected()
    assert window.table.get_children() == ()
    window.close()


def test_dispatcher_runs_calls_from_other_thread(root):
    from pcx_agent.tray.dispatcher import Dispatcher

    dispatcher = Dispatcher(root)
    ran = []
    threading.Thread(target=lambda: dispatcher.call(lambda: ran.append(1))).start()
    deadline = time.monotonic() + 1
    while not ran and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    assert ran == [1]


def test_dispatcher_survives_a_failing_call(root, caplog):
    """Uma acao do menu que falha nao pode travar as proximas (nem o Sair)."""
    import logging

    from pcx_agent.tray.dispatcher import Dispatcher

    dispatcher = Dispatcher(root)
    ran = []

    def broken():
        raise OSError("pasta de logs sumiu")

    with caplog.at_level(logging.ERROR, logger="pcx_agent.tray"):
        dispatcher.call(broken)
        dispatcher.call(lambda: ran.append(1))
        deadline = time.monotonic() + 1
        while not ran and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
    assert ran == [1]
    assert any("pasta de logs sumiu" in (r.exc_text or "") or r.exc_info for r in caplog.records)


def test_tk_callback_errors_go_to_the_log(root, caplog):
    import logging

    from pcx_agent.tray.dispatcher import Dispatcher

    Dispatcher(root)
    with caplog.at_level(logging.ERROR, logger="pcx_agent.tray"):
        try:
            raise ValueError("botao quebrado")
        except ValueError as exc:
            root.report_callback_exception(type(exc), exc, exc.__traceback__)
    assert any(r.exc_info and r.exc_info[0] is ValueError for r in caplog.records)
