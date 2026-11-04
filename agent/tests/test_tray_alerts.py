"""Diagnostico automatico e alerta na bandeja (sem Tk: relogio, agenda e segundo plano falsos)."""

from concurrent.futures import Future
from types import SimpleNamespace

import pytest

from pcx_agent.diagnostics.model import CheckResult
from pcx_agent.diagnostics.monitor import DiagnosticsMonitor
from pcx_agent.diagnostics.runner import ALL_CHECKS, QUICK_CHECKS
from pcx_agent.tray import texts
from pcx_agent.tray.alerts import AlertScheduler


def res(id_: str, status: str = "problema") -> CheckResult:
    return CheckResult(id_, "Grupo", f"Titulo {id_}", status, "")  # type: ignore[arg-type]


class Harness:
    """Agenda, segundo plano e `ui` falsos. `defer` guarda o trabalho em vez de rodar na hora."""

    def __init__(self, defer: bool = False) -> None:
        self.defer = defer
        self.runs: list[set[str] | None] = []
        self.scheduled: list[tuple[int, object]] = []
        self.queued: list = []
        self.ui_log: list[str] = []
        self.in_ui = False
        self.outside_ui_calls: list[str] = []
        self.answers: dict = {}
        self.maintenance_calls = 0
        self.changes: list[frozenset[str]] = []
        self.notified: list[CheckResult] = []

        def changed(ids):
            self.changes.append(ids)
            if not self.in_ui:
                self.outside_ui_calls.append("change")

        def notify(result):
            self.notified.append(result)
            if not self.in_ui:
                self.outside_ui_calls.append("notify")

        self.monitor = DiagnosticsMonitor(changed, notify, clock=lambda: 0.0)
        self.scheduler = AlertScheduler(
            run=self._run,
            monitor=self.monitor,
            schedule=lambda ms, fn: self.scheduled.append((ms, fn)),
            background=self._background,
            ui=self._ui,
            maintenance=self._maintenance,
        )

    def _run(self, ids):
        self.runs.append(ids)
        return self.answers.get(None if ids is None else frozenset(ids), [])

    def _maintenance(self):
        self.maintenance_calls += 1

    def _background(self, work):
        future: Future = Future()
        if self.defer:
            self.queued.append((work, future))
        else:
            future.set_result(work())
        return future

    def _ui(self, fn):
        self.ui_log.append("ui")
        self.in_ui = True
        try:
            fn()
        finally:
            self.in_ui = False

    def fire_next(self):
        _, fn = self.scheduled.pop(0)
        fn()

    def finish_next(self):
        work, future = self.queued.pop(0)
        future.set_result(work())


def test_first_full_run_after_10s_then_quick_every_5min():
    h = Harness()
    h.scheduler.start()
    assert [ms for ms, _ in h.scheduled] == [10_000]
    assert h.runs == []
    h.fire_next()
    assert h.runs == [None]
    assert [ms for ms, _ in h.scheduled] == [300_000]
    h.fire_next()
    assert h.runs == [None, set(QUICK_CHECKS)]
    assert [ms for ms, _ in h.scheduled] == [300_000]
    assert h.maintenance_calls == 2


def test_trigger_while_running_keeps_a_single_pending_request():
    h = Harness(defer=True)
    h.scheduler.trigger({"agente.local"})
    h.scheduler.trigger({"rede.ip"})
    h.scheduler.trigger({"sensores.leitura"})
    assert len(h.queued) == 1  # sem fila: uma rodada por vez
    h.finish_next()
    assert len(h.queued) == 1  # um unico pedido guardado (a uniao)
    h.finish_next()
    assert h.runs == [{"agente.local"}, {"rede.ip", "sensores.leitura"}]
    assert h.queued == []
    h.scheduler.trigger({"rede.ip"})  # livre de novo
    assert len(h.queued) == 1


def test_pending_full_run_survives_narrower_triggers():
    h = Harness(defer=True)
    h.scheduler.trigger({"rede.ip"})
    h.scheduler.trigger(None)
    h.scheduler.trigger({"agente.local"})  # nao troca o pedido completo
    h.finish_next()
    h.finish_next()
    assert h.runs == [{"rede.ip"}, None]


def test_pending_sets_are_merged():
    h = Harness(defer=True)
    h.scheduler.trigger({"rede.ip"})
    h.scheduler.trigger({"agente.local"})
    h.scheduler.trigger({"sensores.gpu"})
    h.finish_next()
    h.finish_next()
    assert h.runs == [{"rede.ip"}, {"agente.local", "sensores.gpu"}]


def test_launch_failure_does_not_leave_scheduler_stuck():
    h = Harness()
    real = h.scheduler._background

    def broken(work):
        raise RuntimeError("sem thread")

    h.scheduler._background = broken
    h.scheduler.trigger({"rede.ip"})
    h.scheduler._background = real
    h.scheduler.trigger({"rede.tipo"})
    assert h.runs == [{"rede.tipo"}]


def test_maintenance_runs_even_when_check_run_fails():
    h = Harness()

    def boom(ids):
        raise RuntimeError("falhou")

    h.scheduler._run = boom
    h.scheduler.trigger({"rede.ip"})
    assert h.maintenance_calls == 1


def test_failed_run_does_not_block_next():
    h = Harness()

    def boom(ids):
        raise RuntimeError("falhou")

    h.scheduler._run = boom
    h.scheduler.trigger({"rede.ip"})
    h.scheduler._run = h._run
    h.scheduler.trigger({"rede.ip"})
    assert h.runs == [{"rede.ip"}]


def test_callbacks_go_through_ui_only():
    h = Harness()
    h.answers[frozenset({"rede.tipo"})] = [res("rede.tipo")]
    h.scheduler.trigger({"rede.tipo"})
    assert h.changes == [frozenset({"rede.tipo"})]
    assert [r.id for r in h.notified] == ["rede.tipo"]
    assert h.outside_ui_calls == []
    assert h.ui_log  # passou pelo ui
    h.answers[frozenset({"rede.tipo"})] = []
    h.scheduler.trigger({"rede.tipo"})
    assert h.changes[-1] == frozenset()
    assert h.outside_ui_calls == []


def test_window_results_feed_monitor():
    h = Harness()
    h.scheduler.feed([res("rede.ip", "atencao")], set(ALL_CHECKS))
    assert h.monitor.alert_ids == frozenset({"rede.ip"})
    assert h.outside_ui_calls == []
    # rodada completa sem o resultado: o alerta de quem rodou e nao devolveu nada apaga
    h.scheduler.feed([], set(ALL_CHECKS))
    assert h.monitor.alert_ids == frozenset()


def test_full_run_clears_ids_that_returned_nothing():
    h = Harness()
    h.answers[frozenset({"agente.encerramento"})] = [res("agente.encerramento", "atencao")]
    h.scheduler.trigger({"agente.encerramento"})
    assert h.monitor.alert_ids == frozenset({"agente.encerramento"})
    h.answers[None] = []
    h.scheduler.trigger(None)
    assert h.monitor.alert_ids == frozenset()


# --- TrayApp (o pystray so e dependencia no Windows: sem ele, estes testes pulam) ---

pytest.importorskip("pystray")
from pcx_agent.tray.app import TrayApp
from pcx_agent.tray.icon import TrayActions


class FakeIcon:
    def __init__(self) -> None:
        self.icon = None
        self.title = ""
        self._menu = None
        self.updates = 0
        self.notices: list[tuple[str, str]] = []

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, value) -> None:  # como o pystray: atribuir o menu ja atualiza
        self._menu = value
        self.update_menu()

    def update_menu(self) -> None:
        self.updates += 1

    def notify(self, message, title=None) -> None:
        self.notices.append((message, title))


def noop() -> None:
    return None


def make_app(tmp_path, server=None, **controller_attrs):
    controller = SimpleNamespace(status_text=lambda: "status", **controller_attrs)
    app = TrayApp(SimpleNamespace(log_dir=tmp_path), server, controller, None)
    app.icon = FakeIcon()
    app._actions = TrayActions(noop, noop, noop, noop, noop, lambda: False, noop, noop)
    return app


def items(app):
    return {item.text: item for item in app.icon.menu.items if hasattr(item, "text")}


def test_set_alert_swaps_icon_tooltip_and_menu(tmp_path):
    app = make_app(tmp_path)
    app.set_alert(frozenset({"rede.tipo"}))
    assert app.icon.title == texts.TOOLTIP_ALERT
    assert texts.MENU_DIAGNOSTICS_ALERT in items(app)
    assert texts.MENU_DIAGNOSTICS not in items(app)
    alert_image = app.icon.icon
    app.set_alert(frozenset())
    assert app.icon.title == "status"
    assert texts.MENU_DIAGNOSTICS in items(app)
    assert texts.MENU_DIAGNOSTICS_ALERT not in items(app)
    assert app.icon.icon.tobytes() != alert_image.tobytes()
    assert app.icon.updates == 2  # uma por troca de menu (o setter faz o update)


def test_default_action_is_diagnostics_while_alert(tmp_path):
    app = make_app(tmp_path)
    app.set_alert(frozenset({"rede.tipo"}))
    defaults = [i.text for i in app.icon.menu.items if getattr(i, "default", False)]
    assert defaults == [texts.MENU_DIAGNOSTICS_ALERT]
    app.set_alert(frozenset())
    defaults = [i.text for i in app.icon.menu.items if getattr(i, "default", False)]
    assert defaults == [texts.MENU_PAIR]


def test_notify_uses_icon_notify_and_swallows_errors(tmp_path):
    app = make_app(tmp_path)
    app.notify(res("rede.tipo"))
    assert app.icon.notices == [("Titulo rede.tipo", texts.APP_NAME)]

    def broken(message, title=None):
        raise OSError

    app.icon.notify = broken
    app.notify(res("rede.tipo"))  # nao propaga


@pytest.mark.parametrize(("start_error", "expected"), [("port_in_use", [{"agente.local"}]), (None, [])])
def test_port_in_use_triggers_agent_check_on_start(tmp_path, monkeypatch, start_error, expected):
    runs: list = []
    hooks = {}
    controller_attrs = {
        "run_checks": lambda ids: runs.append(ids) or [],
        "on_results": None,
        "watch_sensor_failures": lambda cb: hooks.setdefault("cb", cb),
    }
    app = make_app(tmp_path, server=SimpleNamespace(start_error=start_error), **controller_attrs)
    scheduled = []
    app.root = SimpleNamespace(after=lambda ms, fn: scheduled.append((ms, fn)))
    app.dispatcher = SimpleNamespace(call=lambda fn: fn())

    def sync(work):
        future: Future = Future()
        future.set_result(work())
        return future

    monkeypatch.setattr("pcx_agent.tray.app.in_background", sync)
    app._start_alerts()
    assert runs == expected
    assert scheduled[0][0] == 10_000
    assert app.controller.on_results is not None
    hooks["cb"]()  # falha do sensor dispara a rodada dos sensores
    assert runs[-1] == {"sensores.leitura", "sensores.gpu"}


def test_windows_session_end_marks_normal_exit_once_and_quits(tmp_path):
    """Desligar/sair do Windows (WM_QUERYENDSESSION vira WM_SAVE_YOURSELF no Tk): com a
    Inicializacao rapida o boot nao muda, entao a saida normal tem que ficar gravada antes."""
    import tkinter as tk

    from pcx_agent import crashlog

    stopped: list[str] = []
    server = SimpleNamespace(stop=lambda: stopped.append("server"))
    app = make_app(tmp_path, server=server)
    app.icon.stop = lambda: stopped.append("icon")
    crashlog.install_crash_logging(tmp_path)
    app.root = tk.Tk()
    app.root.withdraw()
    try:
        app._watch_session_end()
        command = app.root.protocol("WM_SAVE_YOURSELF")
        assert command
        app.root.tk.call(command)
        app.root.tk.call(command)
    finally:
        app.root.destroy()
    crashlog.uninstall_crash_logging()
    lines = (tmp_path / crashlog.CRASH_FILE).read_text(encoding="utf-8").splitlines()
    assert lines.count(crashlog.ENDED_NORMALLY) == 1
    assert stopped[:2] == ["server", "icon"]
