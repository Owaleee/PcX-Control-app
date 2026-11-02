"""Janela "Trocar senha": nao pede a antiga; pergunta se desconecta todos os celulares."""

from tkinter import messagebox

from pcx_agent.controller import MISMATCH_MESSAGE, PasswordInputError
from pcx_agent.tray import texts
from pcx_agent.tray.theme import GAP, SPACE
from pcx_agent.tray.widgets import (
    BaseWindow,
    PasswordField,
    button_row,
    heading,
    primary_button,
    secondary_button,
)


class PasswordWindow(BaseWindow):
    size_key = "password"
    title_text = texts.TITLE_PASSWORD

    def __init__(self, root, controller) -> None:
        super().__init__(root, controller)
        self.confirm = lambda text: messagebox.askyesno(texts.APP_NAME, text, parent=self)
        heading(self.body, texts.PASSWORD_HEADING, texts.PASSWORD_SUBTITLE).pack(fill="x")
        self.password_field = PasswordField(self.body, texts.NEW_PASSWORD_LABEL)
        self.password_field.pack(fill="x", pady=(GAP + 2, 0))
        self.confirm_field = PasswordField(self.body, texts.CONFIRM_NEW_LABEL)
        self.confirm_field.pack(fill="x", pady=(SPACE[1], 0))
        row = button_row(self.body)
        primary_button(row, texts.SAVE, self.primary_action).pack(side="right")
        secondary_button(row, texts.CANCEL, self.close).pack(side="right", padx=(0, SPACE[1]))
        self.password_field.entry.focus_set()

    def primary_action(self) -> None:
        self.password_field.clear_error()
        self.confirm_field.clear_error()
        try:
            self.controller.set_password(self.password_field.value(), self.confirm_field.value())
        except PasswordInputError as err:
            field = self.confirm_field if err.message == MISMATCH_MESSAGE else self.password_field
            field.show_error(err.message)
            return
        if self.confirm(texts.ASK_REVOKE_ALL):
            self.controller.revoke_all()
        self.close()
