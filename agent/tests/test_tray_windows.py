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


@pytest.fixture(scope="module")
def _tk_root():
    # Um Tk por arquivo: criar varios seguidos falha de vez em quando no runner do Windows
    # ("Can't find a usable tk.tcl").
    # O Python do runner do Windows as vezes nao encontra arquivos do Tk na primeira tentativa.
    for attempt in range(3):
        try:
            window = tk.Tk()
            break
        except tk.TclError:
            if attempt == 2:
                raise
            time.sleep(2)
    window.withdraw()
    from pcx_agent.tray.widgets import apply_style

    apply_style(window)
    yield window
    window.destroy()


@pytest.fixture
def root(_tk_root):
    from pcx_agent.tray.widgets import BaseWindow

    yield _tk_root
    BaseWindow._open.clear()
    for child in _tk_root.winfo_children():
        child.destroy()
    _tk_root.report_callback_exception = tk.Tk.report_callback_exception.__get__(_tk_root)


@pytest.fixture
def controller(tmp_path):
    from pcx_agent.api.app import build_context
    from pcx_agent.config import load_settings
    from pcx_agent.controller import AgentController
    from pcx_agent.sensors.fake import FakeSensorProvider

    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider(seed=2))
    yield AgentController(
        ctx, 8765, address_lookup=lambda: ("192.168.0.15", "Ethernet"),
        category_lookup=lambda _name: None,
    )
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


def _fully_visible(window, widget) -> bool:
    window.update_idletasks()
    bottom = widget.winfo_rooty() + widget.winfo_height()
    inside = bottom <= window.winfo_rooty() + window.winfo_height()
    # Sem espaco, o tkinter espreme o widget: conta como cortado.
    return widget.winfo_ismapped() and inside and widget.winfo_height() >= widget.winfo_reqheight()


def _find(widget, text):
    if str(widget.cget("text") if "text" in widget.keys() else "") == text:  # noqa: SIM118 - opcoes do Tk
        return widget
    for child in widget.winfo_children():
        found = _find(child, text)
        if found is not None:
            return found
    return None


def test_first_run_step_two_shows_ip_and_finish(root, controller):
    """Print do Alexandre: no passo 2 o endereco do PC e o "Concluir" ficavam cortados."""
    from pcx_agent.tray.first_run import FirstRunWindow

    window = FirstRunWindow.show(root, controller)
    window.password_field.set_value("senha-boa-1")
    window.confirm_field.set_value("senha-boa-1")
    window.primary_action()
    for _ in range(5):
        root.update()
    assert _fully_visible(window, _find(window, "192.168.0.15:8765"))
    assert _fully_visible(window, _find(window, "Concluir"))
    window.close()


def test_pairing_window_shows_ip_and_close(root, controller):
    from pcx_agent.tray.pairing import PairingWindow

    window = PairingWindow.show(root, controller)
    for _ in range(5):
        root.update()
    assert _fully_visible(window, _find(window, "192.168.0.15:8765"))
    assert _fully_visible(window, _find(window, "Fechar"))
    window.close()


def _public_controller(tmp_path, category):
    from pcx_agent.api.app import build_context
    from pcx_agent.config import load_settings
    from pcx_agent.controller import AgentController
    from pcx_agent.sensors.fake import FakeSensorProvider

    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider(seed=2))
    return ctx, AgentController(
        ctx, 8765, address_lookup=lambda: ("192.168.18.22", "Ethernet"),
        category_lookup=lambda _name: category,
    )


def _settle(root, seconds=2.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)


@pytest.mark.parametrize("window_name", ["pairing", "first_run"])
def test_public_network_banner_shows_and_keeps_buttons_visible(root, tmp_path, window_name):
    from pcx_agent.controller import PUBLIC_NETWORK_WARNING
    from pcx_agent.tray import texts
    from pcx_agent.tray.first_run import FirstRunWindow
    from pcx_agent.tray.pairing import PairingWindow

    ctx, controller = _public_controller(tmp_path, "public")
    try:
        if window_name == "pairing":
            window, last_button = PairingWindow.show(root, controller), texts.CLOSE
        else:
            window = FirstRunWindow.show(root, controller)
            window.password_field.set_value("senha-boa-1")
            window.confirm_field.set_value("senha-boa-1")
            window.primary_action()
            last_button = texts.FINISH
        _settle(root)
        assert _fully_visible(window, _find(window, PUBLIC_NETWORK_WARNING))
        assert _fully_visible(window, _find(window, texts.OPEN_NETWORK_SETTINGS))
        assert _fully_visible(window, _find(window, "192.168.18.22:8765"))
        assert _fully_visible(window, _find(window, last_button))
        window.close()
    finally:
        ctx.db.close()


def test_private_network_has_no_banner(root, tmp_path):
    from pcx_agent.controller import PUBLIC_NETWORK_WARNING
    from pcx_agent.tray.pairing import PairingWindow

    ctx, controller = _public_controller(tmp_path, "private")
    try:
        window = PairingWindow.show(root, controller)
        _settle(root, 1.0)
        assert _find(window, PUBLIC_NETWORK_WARNING) is None
        window.close()
    finally:
        ctx.db.close()


def test_repeated_network_checks_do_not_pile_up(root):
    """Varios cliques em "Gerar outro codigo" nao enfileiram PowerShell nem piscam a faixa."""
    import threading

    from pcx_agent.tray.network_banner import NetworkWarningSlot

    calls, running, peak = [], [0], [0]
    lock = threading.Lock()

    class SlowController:
        def public_network_warning(self, info):
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.3)
            calls.append(info)
            with lock:
                running[0] -= 1
            return f"aviso {info}"

    changes = []
    slot = NetworkWarningSlot(root, on_change=changes.append)
    slot.pack()
    for info in range(5):
        slot.check(SlowController(), info)
        root.update()
    _settle(root, 1.5)
    assert len(calls) <= 2
    assert calls[-1] == 4
    assert changes[-1] == "aviso 4"
    assert None not in changes  # sem piscar: a faixa nao some entre uma checagem e outra
    slot.destroy()


class _DiagnosticsController:
    """Controlador falso: resultados prontos, sem PowerShell."""

    def __init__(self, results):
        self.results = results
        self.runs = 0
        self.fixes = []

    def run_diagnostics(self):
        self.runs += 1
        return self.results

    def diagnostics_report(self, results):
        return f"relatorio com {len(results)} itens"

    last_fix_message = None
    program = r"C:\Programa\PcXControl.exe"

    def apply_fix(self, fix):
        self.fixes.append(fix)
        return True

    def program_path(self):
        return self.program


def _diag_results():
    from pcx_agent.diagnostics.model import CheckResult

    return [
        CheckResult("rede.ip", "Rede e firewall", "IP da rede local", "ok", "192.168.18.22 na placa Ethernet."),
        CheckResult(
            "rede.tipo", "Rede e firewall", "Tipo de rede no Windows", "problema",
            "A rede da placa Ethernet está como Pública: o Windows bloqueia o celular. Mude para Privada.",
            "abrir_rede",
        ),
        CheckResult(
            "rede.firewall", "Rede e firewall", "Regra do firewall", "problema",
            'A regra "PcX Control - agente" não existe: o Windows bloqueia o celular. Crie a regra de novo.',
            "criar_firewall",
        ),
        CheckResult("rede.vpn", "Rede e firewall", "VPN", "atencao", "VPN ligada: Radmin VPN."),
        CheckResult("agente.local", "Agente acessível", "Agente respondendo na rede", "ok", "Responde."),
        CheckResult("antivirus.terceiros", "Antivírus", "Avast Antivirus", "atencao", "Libere o PcX Control nele."),
        CheckResult("sensores.gpu", "Sensores", "AMD Radeon RX 7600", "info", "Fabricante: AMD."),
        CheckResult("sensores.leitura", "Sensores", "Leitura dos sensores", "ok", "Lidos."),
    ]


def _open_diagnostics(root, controller):
    from pcx_agent.tray.diagnostics_window import DiagnosticsWindow

    window = DiagnosticsWindow.show(root, controller)
    deadline = time.monotonic() + 5
    while not window.results and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    for _ in range(5):
        root.update()
    return window


def test_diagnostics_lists_results_with_summary_and_fixes(root):
    from pcx_agent.tray import texts

    controller = _DiagnosticsController(_diag_results())
    window = _open_diagnostics(root, controller)
    assert controller.runs == 1
    assert window.status.cget("text") == texts.DIAG_SUMMARY_PROBLEMS.format(n=2)
    for text in ("Rede e firewall", "Antivírus", "Sensores", "AMD Radeon RX 7600", "Avast Antivirus"):
        assert _find(window, text) is not None, text
    assert [b.cget("text") for b in window.results_list.fix_buttons] == [
        texts.DIAG_FIX_NETWORK, texts.DIAG_FIX_FIREWALL,
    ]
    window.close()


def test_diagnostics_fix_buttons_call_the_controller_and_rerun_on_focus(root):
    controller = _DiagnosticsController(_diag_results())
    window = _open_diagnostics(root, controller)
    window.results_list.fix_buttons[0].invoke()
    window.results_list.fix_buttons[1].invoke()
    assert controller.fixes == ["abrir_rede", "criar_firewall"]
    window.event_generate("<FocusIn>")
    deadline = time.monotonic() + 5
    while controller.runs < 2 and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    assert controller.runs == 2
    window.close()


def test_diagnostics_copy_report_goes_to_clipboard(root):
    from pcx_agent.tray import texts

    window = _open_diagnostics(root, _DiagnosticsController(_diag_results()))
    window.copy_report()
    assert root.clipboard_get() == "relatorio com 8 itens"
    assert window.status.cget("text") == texts.DIAG_COPIED
    window.close()


def test_diagnostics_footer_buttons_are_not_cut(root):
    from pcx_agent.tray import texts

    window = _open_diagnostics(root, _DiagnosticsController(_diag_results()))
    for text in (texts.DIAG_COPY, texts.DIAG_AGAIN, texts.CLOSE):
        assert _fully_visible(window, _find(window, text)), text
    window.close()


def test_diagnostics_all_ok_summary(root):
    from pcx_agent.diagnostics.model import CheckResult
    from pcx_agent.tray import texts

    ok = [CheckResult("rede.ip", "Rede e firewall", "IP", "ok", "ok")]
    window = _open_diagnostics(root, _DiagnosticsController(ok))
    assert window.status.cget("text") == texts.DIAG_SUMMARY_OK
    window.close()


def test_diagnostics_failure_keeps_the_window_usable(root, caplog):
    class Broken(_DiagnosticsController):
        def run_diagnostics(self):
            self.runs += 1
            raise RuntimeError("quebrou")

    from pcx_agent.tray.diagnostics_window import DiagnosticsWindow

    controller = Broken([])
    window = DiagnosticsWindow.show(root, controller)
    _settle(root, 1.0)
    assert str(window.again_button.cget("state")) == "normal"
    assert any("Diagnostico falhou" in r.getMessage() for r in caplog.records)
    window.close()


def test_diagnostics_run_in_a_daemon_thread():
    """Sair pela bandeja no meio de um diagnostico nao espera o PowerShell terminar."""
    import threading as th

    from pcx_agent.tray.diagnostics_window import in_background

    seen = []
    future = in_background(lambda: seen.append(th.current_thread().daemon) or 42)
    assert future.result(timeout=5) == 42
    assert seen == [True]


def test_firewall_fix_runs_in_background_and_checks_again_when_done(root):
    controller = _DiagnosticsController(_diag_results())
    window = _open_diagnostics(root, controller)
    window.results_list.fix_buttons[1].invoke()  # criar_firewall
    deadline = time.monotonic() + 5
    while controller.runs < 2 and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    assert controller.fixes == ["criar_firewall"]
    assert controller.runs == 2  # verificou de novo sem precisar voltar o foco
    window.close()


def test_rows_show_new_fix_buttons(root):
    from pcx_agent.diagnostics.model import CheckResult
    from pcx_agent.tray import texts

    results = [
        CheckResult("sensores.leitura", "Sensores", "Leitura", "problema", "Parada.", "reiniciar_sensores"),
        CheckResult("agente.local", "Agente acessível", "Agente", "problema", "Fora.", "reiniciar_servidor"),
        CheckResult("agente.porta", "Agente acessível", "Porta", "problema", "Em uso.", "trocar_porta"),
        CheckResult("antivirus.terceiros", "Antivírus", "Avast", "atencao", "Libere.", "copiar_caminho"),
    ]
    window = _open_diagnostics(root, _DiagnosticsController(results))
    assert [b.cget("text") for b in window.results_list.fix_buttons] == [
        texts.DIAG_FIX_SENSORS, texts.DIAG_FIX_RESTART, texts.DIAG_FIX_PORT, texts.DIAG_FIX_COPY_PATH,
    ]
    window.close()


def test_copy_path_puts_exe_in_clipboard(root):
    from pcx_agent.diagnostics.model import CheckResult
    from pcx_agent.tray import texts

    results = [CheckResult("antivirus.terceiros", "Antivírus", "Avast", "atencao", "Libere.", "copiar_caminho")]
    controller = _DiagnosticsController(results)
    window = _open_diagnostics(root, controller)
    window.results_list.fix_buttons[0].invoke()
    assert root.clipboard_get() == controller.program
    assert window.status.cget("text") == texts.DIAG_PATH_COPIED
    assert controller.fixes == []  # a janela cuida da area de transferencia
    window.close()


def test_any_fix_runs_diagnostics_again_and_shows_the_message(root):
    from pcx_agent.diagnostics.model import CheckResult

    results = [CheckResult("agente.porta", "Agente acessível", "Porta", "problema", "Em uso.", "trocar_porta")]
    controller = _DiagnosticsController(results)
    controller.last_fix_message = "Porta trocada para 8766."
    window = _open_diagnostics(root, controller)
    window.results_list.fix_buttons[0].invoke()
    deadline = time.monotonic() + 5
    while controller.runs < 2 and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    for _ in range(10):
        root.update()
        time.sleep(0.02)
    assert controller.fixes == ["trocar_porta"]
    assert controller.runs == 2
    assert window.status.cget("text") == "Porta trocada para 8766."
    assert controller.last_fix_message is None  # mostrada uma vez
    window.close()
