"""Primeira execucao: passo 1 cria a senha, passo 2 mostra o QR."""

import tkinter as tk
from collections.abc import Callable

from pcx_agent.controller import MISMATCH_MESSAGE, PasswordInputError
from pcx_agent.tray import texts
from pcx_agent.tray.pairing import PairingFrame
from pcx_agent.tray.theme import COLORS, FONTS, GAP, SPACE
from pcx_agent.tray.widgets import (
    BaseWindow,
    PasswordField,
    button_row,
    heading,
    label,
    primary_button,
    secondary_button,
)


class FirstRunWindow(BaseWindow):
    size_key = "first_run"
    title_text = texts.TITLE_FIRST_RUN

    def __init__(self, root, controller, on_done: Callable[[], None] | None = None) -> None:
        super().__init__(root, controller)
        self._on_done = on_done
        self.step = 1
        self._steps = tk.Frame(self.body, bg=COLORS["background"])
        self._steps.pack(fill="x", pady=(0, GAP + 4))
        self._content = tk.Frame(self.body, bg=COLORS["background"])
        self._content.pack(fill="both", expand=True)
        self._draw_steps()
        self._build_password_step()

    def _draw_steps(self) -> None:
        for child in self._steps.winfo_children():
            child.destroy()
        for number, name in ((1, texts.STEP_PASSWORD), (2, texts.STEP_PAIR)):
            current = number == self.step
            done = number < self.step
            circle = tk.Label(
                self._steps, text=str(number), width=2, font=FONTS["step"],
                bg=COLORS["accent"] if current or done else COLORS["background"],
                fg=COLORS["on_accent"] if current or done else COLORS["text_muted"],
                highlightthickness=0 if current or done else 1,
                highlightbackground=COLORS["border_strong"],
            )
            circle.pack(side="left")
            label(self._steps, name, font="body_bold" if current else "small",
                  color="text" if current else "text_muted").pack(side="left", padx=(SPACE[1], 0))
            if number == 1:
                tk.Frame(self._steps, bg=COLORS["border_strong"], height=1, width=32).pack(
                    side="left", padx=SPACE[1]
                )

    def _build_password_step(self) -> None:
        heading(self._content, texts.FIRST_RUN_HEADING, texts.FIRST_RUN_SUBTITLE).pack(fill="x")
        self.password_field = PasswordField(self._content, texts.PASSWORD_LABEL)
        self.password_field.pack(fill="x", pady=(GAP + 4, 0))
        self.confirm_field = PasswordField(self._content, texts.CONFIRM_LABEL)
        self.confirm_field.pack(fill="x", pady=(SPACE[1], 0))
        row = button_row(self._content)
        primary_button(row, texts.CONTINUE, self.primary_action).pack(side="right")
        secondary_button(row, texts.LATER, self.close).pack(side="right", padx=(0, SPACE[1]))
        self.password_field.entry.focus_set()

    def primary_action(self) -> None:
        if self.step == 2:
            self._finish()
            return
        self.password_field.clear_error()
        self.confirm_field.clear_error()
        try:
            self.controller.set_password(self.password_field.value(), self.confirm_field.value())
        except PasswordInputError as err:
            field = self.confirm_field if err.message == MISMATCH_MESSAGE else self.password_field
            field.show_error(err.message)
            return
        self.step = 2
        self.resize_to("first_run_pair")
        self._draw_steps()
        for child in self._content.winfo_children():
            child.destroy()
        PairingFrame(self._content, self.controller, texts.FINISH, self._finish).pack(
            fill="both", expand=True
        )

    def _finish(self) -> None:
        if self._on_done is not None:
            self._on_done()
        self.close()
