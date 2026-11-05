"""TrayApp: junta servidor, controlador, icone e janelas.

Threads: o tkinter roda na thread principal; o pystray roda destacado e o servidor
numa thread propria. Tudo que vem de fora passa pelo Dispatcher.
"""

import logging
import os
import tkinter as tk

from pcx_agent import crashlog
from pcx_agent.diagnostics.model import CheckResult
from pcx_agent.diagnostics.monitor import DiagnosticsMonitor
from pcx_agent.tray import texts
from pcx_agent.tray.alerts import AlertScheduler
from pcx_agent.tray.devices import DevicesWindow
from pcx_agent.tray.diagnostics_window import DiagnosticsWindow, in_background
from pcx_agent.tray.dispatcher import Dispatcher
from pcx_agent.tray.first_run import FirstRunWindow
from pcx_agent.tray.icon import TrayActions, build_menu, build_tray_icon, tray_image
from pcx_agent.tray.pairing import PairingFrame, PairingWindow
from pcx_agent.tray.password import PasswordWindow
from pcx_agent.tray.widgets import apply_style

STATUS_REFRESH_MS = 2000
logger = logging.getLogger("pcx_agent.tray")


class TrayApp:
    def __init__(self, settings, server, controller, autostart) -> None:
        self.settings = settings
        self.server = server
        self.controller = controller
        self.autostart = autostart
        self._actions: TrayActions | None = None
        self._alert_ids: frozenset[str] = frozenset()

    def run(self) -> int:
        self.root = tk.Tk()
        self.root.withdraw()
        apply_style(self.root)
        self.dispatcher = Dispatcher(self.root)
        self.controller.on_paired = lambda name: self.dispatcher.call(lambda: self._paired(name))
        ui = self.dispatcher.call
        self._actions = TrayActions(
            pair=lambda: ui(self.open_pairing),
            devices=lambda: ui(lambda: DevicesWindow.show(self.root, self.controller)),
            diagnostics=lambda: ui(lambda: DiagnosticsWindow.show(self.root, self.controller)),
            password=lambda: ui(lambda: PasswordWindow.show(self.root, self.controller)),
            toggle_autostart=lambda: ui(self.toggle_autostart),
            autostart_checked=self.autostart.is_enabled,
            open_logs=lambda: ui(self.open_logs),
            quit=lambda: ui(self.quit),
        )
        self.icon = build_tray_icon(self.controller, self._actions)
        self.icon.run_detached()
        self._watch_session_end()
        self._start_alerts()
        if self.controller.needs_first_run():
            FirstRunWindow.show(self.root, self.controller)
        self._refresh_status()
        logger.info("Bandeja iniciada na porta %s", self.settings.port)
        self.root.mainloop()
        return 0

    def _start_alerts(self) -> None:
        """Diagnostico automatico: 1a rodada em 10 s, depois as rapidas a cada 5 min."""
        monitor = DiagnosticsMonitor(self.set_alert, self.notify)
        scheduler = AlertScheduler(
            run=self.controller.run_checks,
            monitor=monitor,
            schedule=lambda ms, fn: self.root.after(ms, fn),
            background=in_background,
            ui=self.dispatcher.call,
            maintenance=lambda: crashlog.maintenance(self.settings.log_dir),
        )
        self.controller.on_results = scheduler.feed
        self.controller.watch_sensor_failures(
            lambda: scheduler.trigger({"sensores.leitura", "sensores.gpu"})
        )
        scheduler.start()
        if getattr(self.server, "start_error", None) == "port_in_use":
            scheduler.trigger({"agente.local"})

    def set_alert(self, ids: frozenset[str]) -> None:
        """Acende ou apaga o alerta: imagem, dica e menu (a acao padrao troca junto)."""
        was = bool(self._alert_ids)
        self._alert_ids = ids
        alert = bool(ids)
        self.icon.icon = tray_image(alert)
        self.icon.title = texts.TOOLTIP_ALERT if alert else self.controller.status_text()
        if alert != was or self.icon.menu is None:
            self.icon.menu = build_menu(self._actions, alert)  # o setter do pystray ja atualiza o menu

    def notify(self, result: CheckResult) -> None:
        try:
            self.icon.notify(result.title, texts.APP_NAME)
        except (NotImplementedError, OSError):  # notificacao e opcional
            logger.debug("Notificação indisponível", exc_info=True)

    def open_pairing(self) -> None:
        if self.controller.needs_first_run():
            FirstRunWindow.show(self.root, self.controller)
        else:
            PairingWindow.show(self.root, self.controller)

    def _paired(self, name: str) -> None:
        PairingFrame.broadcast_paired(name)
        try:
            self.icon.notify(texts.NOTIFY_PAIRED.format(nome=name), texts.APP_NAME)
        except (NotImplementedError, OSError):  # notificacao e opcional
            logger.debug("Notificação indisponível", exc_info=True)

    def _refresh_status(self) -> None:
        self.icon.title = texts.TOOLTIP_ALERT if self._alert_ids else self.controller.status_text()
        self.root.after(STATUS_REFRESH_MS, self._refresh_status)

    def toggle_autostart(self) -> None:
        if self.autostart.is_enabled():
            self.autostart.disable()
        else:
            self.autostart.enable()
        self.icon.update_menu()

    def open_logs(self) -> None:
        self.settings.log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.settings.log_dir)  # so existe no Windows

    def _watch_session_end(self) -> None:
        """Desligar ou sair do Windows: o Tk traduz WM_QUERYENDSESSION em WM_SAVE_YOURSELF.
        Com a Inicializacao rapida o horario do boot nao muda; sem gravar a saida normal aqui,
        o processo morto no desligamento viraria "fechou inesperadamente" no proximo inicio."""
        self.root.protocol("WM_SAVE_YOURSELF", self._session_ending)

    def _session_ending(self) -> None:
        logger.info("Windows encerrando a sessao")
        crashlog.mark_normal_exit()
        self.quit()

    def quit(self) -> None:
        logger.info("Saindo pela bandeja")
        self.server.stop()
        self.icon.stop()
        self.root.quit()
