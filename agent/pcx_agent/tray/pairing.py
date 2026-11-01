"""Janela "Parear celular": QR, contagem regressiva e os estados expirado, sem rede e pareado."""

import time
import tkinter as tk
from collections.abc import Callable
from typing import ClassVar

from pcx_agent.tray import texts
from pcx_agent.tray.qr import qr_photo
from pcx_agent.tray.theme import COLORS, GAP, QR_PANEL, SPACE
from pcx_agent.tray.widgets import (
    BaseWindow,
    InfoPanel,
    button_row,
    heading,
    label,
    primary_button,
    secondary_button,
)

AUTO_CLOSE_MS = 2000


def _countdown(seconds: float) -> str:
    seconds = max(0, int(seconds + 0.999))
    return f"{seconds // 60}:{seconds % 60:02d}"


class PairingFrame(tk.Frame):
    """O miolo do pareamento; usado na janela propria e no passo 2 da primeira execucao."""

    live: ClassVar[set["PairingFrame"]] = set()

    def __init__(
        self,
        parent,
        controller,
        primary_text: str,
        on_primary: Callable[[], None],
        on_paired: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, bg=parent["bg"])
        self._controller = controller
        self._on_paired = on_paired
        self._expires_at = 0.0
        self._timer: str | None = None
        self._photo = None
        heading(self, texts.PAIRING_HEADING, texts.PAIRING_SUBTITLE).pack(fill="x")
        self._panel = tk.Frame(self, bg=COLORS["qr_background"], width=QR_PANEL, height=QR_PANEL)
        self._panel.pack(pady=(GAP + 2, GAP))
        self._panel.pack_propagate(False)
        self._content = label(self._panel, "", bg=COLORS["qr_background"])
        self._content.pack(expand=True)
        self._countdown = label(self, "", color="text_muted")
        self._countdown.pack()
        self._info = InfoPanel(self, [(texts.ADDRESS_LABEL, ""), (texts.NO_CAMERA_LABEL,
                                                                    texts.NO_CAMERA_HINT)])
        self._info.pack(fill="x", pady=(GAP, 0))
        row = button_row(self)
        secondary_button(row, texts.NEW_CODE, self.refresh).pack(side="left")
        primary_button(row, primary_text, on_primary).pack(side="right")
        PairingFrame.live.add(self)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.refresh()

    @classmethod
    def broadcast_paired(cls, name: str) -> None:
        for frame in list(cls.live):
            frame.show_paired(name)

    def refresh(self) -> None:
        info = self._controller.start_pairing()
        self._info.set_value(0, f"{info.host}:{info.port}")
        if info.warning:
            self._show_state(info.warning, COLORS["danger"])
            self._countdown.configure(text="")
            self._stop_timer()
            return
        self._photo = qr_photo(info.uri)
        self._panel.configure(bg=COLORS["qr_background"], highlightthickness=0)
        self._content.configure(image=self._photo, text="", bg=COLORS["qr_background"])
        self._expires_at = info.expires_at
        self._tick()

    def _show_state(self, text: str, border: str) -> None:
        self._panel.configure(bg=COLORS["surface"], highlightthickness=1,
                              highlightbackground=border)
        self._content.configure(image="", text=text, bg=COLORS["surface"], fg=COLORS["text"],
                                wraplength=QR_PANEL - SPACE[4], justify="center")

    def _tick(self) -> None:
        self._stop_timer()
        left = self._expires_at - time.time()
        if left <= 0:
            self._show_state(texts.EXPIRED, COLORS["border_strong"])
            self._countdown.configure(text="")
            return
        self._countdown.configure(text=texts.VALID_FOR.format(tempo=_countdown(left)))
        self._timer = self.after(1000, self._tick)

    def _stop_timer(self) -> None:
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None

    def show_paired(self, name: str) -> None:
        self._stop_timer()
        self._countdown.configure(text="")
        self._show_state(texts.PAIRED.format(nome=name), COLORS["accent"])
        if self._on_paired is not None:
            self._on_paired(name)

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self._stop_timer()
            PairingFrame.live.discard(self)


class PairingWindow(BaseWindow):
    size_key = "pairing"
    title_text = texts.TITLE_PAIRING

    def __init__(self, root, controller) -> None:
        super().__init__(root, controller)
        self.frame = PairingFrame(
            self.body, controller, texts.CLOSE, self.close, on_paired=self._paired
        )
        self.frame.pack(fill="both", expand=True)

    def _paired(self, _name: str) -> None:
        self.after(AUTO_CLOSE_MS, lambda: self.winfo_exists() and self.close())

    def on_reopen(self) -> None:
        self.frame.refresh()

    def primary_action(self) -> None:
        self.close()
