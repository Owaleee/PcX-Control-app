"""Aviso de rede Publica: checagem em segundo plano e a faixa com o botao das configuracoes."""

import os
import sys
import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from pcx_agent.tray import texts
from pcx_agent.tray.theme import COLORS, GAP, SPACE
from pcx_agent.tray.widgets import label, secondary_button

NETWORK_SETTINGS_URI = "ms-settings:network-status"
CHECK_POLL_MS = 150
# Ler o tipo de rede chama o PowerShell (~1 s): roda fora da thread da interface.
_CHECKS = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pcx-rede")


def open_network_settings() -> None:
    if sys.platform == "win32":
        os.startfile(NETWORK_SETTINGS_URI)  # abre Configuracoes > Rede e Internet


class NetworkBanner(tk.Frame):
    """A faixa em si: texto do aviso e o botao que abre as configuracoes de rede."""

    def __init__(self, parent, warning: str) -> None:
        super().__init__(
            parent, bg=COLORS["surface"], highlightthickness=1,
            highlightbackground=COLORS["danger"], padx=SPACE[2] - 4, pady=SPACE[1],
        )
        label(self, warning, font="small", color="danger", anchor="w", justify="left",
              wraplength=360).pack(fill="x")
        secondary_button(self, texts.OPEN_NETWORK_SETTINGS, open_network_settings).pack(
            anchor="w", pady=(SPACE[0] + 2, 0)
        )


class NetworkWarningSlot(tk.Frame):
    """Lugar da faixa: checa a rede sem travar a janela e avisa `on_change` (aviso ou None)."""

    def __init__(self, parent, on_change: Callable[[str | None], None]) -> None:
        super().__init__(parent, bg=parent["bg"])
        self._on_change = on_change
        self._check: Future | None = None

    def check(self, controller, info) -> None:
        self.show(None)
        self._check = _CHECKS.submit(controller.public_network_warning, info)
        self.after(CHECK_POLL_MS, self._poll, self._check)

    def _poll(self, check: Future) -> None:
        if check is not self._check or not self.winfo_exists():
            return  # janela fechada ou outro codigo gerado nesse meio-tempo
        if not check.done():
            self.after(CHECK_POLL_MS, self._poll, check)
            return
        try:
            warning = check.result()
        except Exception:  # noqa: BLE001 - sem aviso e melhor que janela quebrada
            warning = None
        self.show(warning)

    def show(self, warning: str | None) -> None:
        for child in self.winfo_children():
            child.destroy()
        if warning:
            NetworkBanner(self, warning).pack(fill="x", pady=(GAP, 0))
        self._on_change(warning)
