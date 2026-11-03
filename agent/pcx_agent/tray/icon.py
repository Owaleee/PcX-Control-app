"""Icone e menu da bandeja (pystray). Os itens so chamam as acoes recebidas."""

from collections.abc import Callable
from dataclasses import dataclass

import pystray
from PIL import Image

from pcx_agent import assets_path
from pcx_agent.tray import texts


@dataclass(frozen=True)
class TrayActions:
    pair: Callable[[], None]
    devices: Callable[[], None]
    diagnostics: Callable[[], None]
    password: Callable[[], None]
    toggle_autostart: Callable[[], None]
    autostart_checked: Callable[[], bool]
    open_logs: Callable[[], None]
    quit: Callable[[], None]


def build_tray_icon(controller, actions: TrayActions) -> pystray.Icon:
    menu = pystray.Menu(
        pystray.MenuItem(texts.MENU_PAIR, lambda: actions.pair(), default=True),
        pystray.MenuItem(texts.MENU_DEVICES, lambda: actions.devices()),
        pystray.MenuItem(texts.MENU_DIAGNOSTICS, lambda: actions.diagnostics()),
        pystray.MenuItem(texts.MENU_PASSWORD, lambda: actions.password()),
        pystray.MenuItem(
            texts.MENU_AUTOSTART,
            lambda: actions.toggle_autostart(),
            checked=lambda _item: actions.autostart_checked(),
        ),
        pystray.MenuItem(texts.MENU_LOGS, lambda: actions.open_logs()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(texts.MENU_QUIT, lambda: actions.quit()),
    )
    image = Image.open(assets_path("tray.png"))
    return pystray.Icon("PcXControl", image, controller.status_text(), menu)
