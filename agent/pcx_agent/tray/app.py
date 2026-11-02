"""TrayApp: junta servidor, controlador, icone e janelas.

Threads: o tkinter roda na thread principal; o pystray roda destacado e o servidor
numa thread propria. Tudo que vem de fora passa pelo Dispatcher.
"""

import logging
import os
import tkinter as tk

from pcx_agent.tray import texts
from pcx_agent.tray.devices import DevicesWindow
from pcx_agent.tray.dispatcher import Dispatcher
from pcx_agent.tray.first_run import FirstRunWindow
from pcx_agent.tray.icon import TrayActions, build_tray_icon
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

    def run(self) -> int:
        self.root = tk.Tk()
        self.root.withdraw()
        apply_style(self.root)
        self.dispatcher = Dispatcher(self.root)
        self.controller.on_paired = lambda name: self.dispatcher.call(lambda: self._paired(name))
        ui = self.dispatcher.call
        self.icon = build_tray_icon(
            self.controller,
            TrayActions(
                pair=lambda: ui(self.open_pairing),
                devices=lambda: ui(lambda: DevicesWindow.show(self.root, self.controller)),
                password=lambda: ui(lambda: PasswordWindow.show(self.root, self.controller)),
                toggle_autostart=lambda: ui(self.toggle_autostart),
                autostart_checked=self.autostart.is_enabled,
                open_logs=lambda: ui(self.open_logs),
                quit=lambda: ui(self.quit),
            ),
        )
        self.icon.run_detached()
        if self.controller.needs_first_run():
            FirstRunWindow.show(self.root, self.controller)
        self._refresh_status()
        logger.info("Bandeja iniciada na porta %s", self.settings.port)
        self.root.mainloop()
        return 0

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
        self.icon.title = self.controller.status_text()
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

    def quit(self) -> None:
        logger.info("Saindo pela bandeja")
        self.server.stop()
        self.icon.stop()
        self.root.quit()
