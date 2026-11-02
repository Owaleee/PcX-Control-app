"""Janela "Celulares pareados": lista, quem esta conectado e desconectar."""

import tkinter as tk
from tkinter import messagebox, ttk

from pcx_agent.tray import texts
from pcx_agent.tray.theme import COLORS, GAP, SPACE
from pcx_agent.tray.widgets import (
    BaseWindow,
    button_row,
    danger_button,
    heading,
    label,
    primary_button,
    secondary_button,
)

REFRESH_MS = 2000
COLUMNS = (("name", texts.COLUMN_NAME, 220), ("last_used", texts.COLUMN_LAST_USED, 160),
           ("status", texts.COLUMN_STATUS, 160))


class DevicesWindow(BaseWindow):
    size_key = "devices"
    title_text = texts.TITLE_DEVICES

    def __init__(self, root, controller) -> None:
        super().__init__(root, controller)
        self.confirm = lambda text: messagebox.askyesno(texts.APP_NAME, text, parent=self)
        heading(self.body, texts.DEVICES_HEADING, texts.DEVICES_SUBTITLE).pack(fill="x")
        box = tk.Frame(self.body, bg=COLORS["background"], highlightthickness=1,
                       highlightbackground=COLORS["border"])
        box.pack(fill="both", expand=True, pady=(GAP, GAP))
        self.table = ttk.Treeview(box, columns=[c[0] for c in COLUMNS], show="headings",
                                  style="Pcx.Treeview", selectmode="browse", height=5)
        for key, title, width in COLUMNS:
            self.table.heading(key, text=title, anchor="w")
            self.table.column(key, width=width, anchor="w")
        self.table.tag_configure("active", background=COLORS["selected"],
                                 foreground=COLORS["accent"])
        self.table.pack(fill="both", expand=True)
        self._empty = label(box, texts.NO_DEVICES, color="text_muted")
        row = button_row(self.body)
        danger_button(row, texts.DISCONNECT_ALL, self._revoke_all).pack(side="left")
        primary_button(row, texts.CLOSE, self.close).pack(side="right")
        secondary_button(row, texts.DISCONNECT, self._revoke_selected).pack(
            side="right", padx=(0, SPACE[1])
        )
        self._timer: str | None = None
        self.refresh()

    def refresh(self) -> None:
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        rows = self.controller.devices()
        for row in rows:
            status = texts.STATUS_ACTIVE if row.active else texts.STATUS_PAIRED
            self.table.insert("", "end", iid=row.id, values=(row.name, row.last_used, status),
                              tags=("active",) if row.active else ())
        if rows:
            self._empty.place_forget()
        else:
            self._empty.place(relx=0.5, rely=0.6, anchor="center")
        keep = [iid for iid in selected if self.table.exists(iid)]
        if keep:
            self.table.selection_set(keep)
        if self._timer is not None:
            self.after_cancel(self._timer)
        self._timer = self.after(REFRESH_MS, self.refresh)

    def _revoke_selected(self) -> None:
        for device_id in self.table.selection():
            self.controller.revoke(device_id)
        self.refresh()

    def _revoke_all(self) -> None:
        if self.table.get_children() and self.confirm(texts.CONFIRM_DISCONNECT_ALL):
            self.controller.revoke_all()
            self.refresh()

    def on_reopen(self) -> None:
        self.refresh()

    def primary_action(self) -> None:
        self.close()

    def close(self) -> None:
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        super().close()
