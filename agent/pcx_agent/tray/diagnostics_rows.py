"""Lista com rolagem dos resultados do diagnostico, agrupada, com o botao de correcao."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from pcx_agent.diagnostics.model import GROUPS, CheckResult
from pcx_agent.tray import texts
from pcx_agent.tray.theme import COLORS, FONTS, SPACE
from pcx_agent.tray.widgets import label, secondary_button

STATUS_COLORS = {"ok": "ok", "atencao": "warning", "problema": "danger", "info": "text_muted"}
STATUS_TEXT = {
    "ok": texts.DIAG_STATUS_OK,
    "atencao": texts.DIAG_STATUS_WARNING,
    "problema": texts.DIAG_STATUS_PROBLEM,
    "info": texts.DIAG_STATUS_INFO,
}
FIX_TEXT = {
    "abrir_rede": texts.DIAG_FIX_NETWORK,
    "criar_firewall": texts.DIAG_FIX_FIREWALL,
    "reiniciar_sensores": texts.DIAG_FIX_SENSORS,
    "reiniciar_servidor": texts.DIAG_FIX_RESTART,
    "trocar_porta": texts.DIAG_FIX_PORT,
    "copiar_caminho": texts.DIAG_FIX_COPY_PATH,
}
DOT = 10
WRAP = 400


class ResultList(tk.Frame):
    """Canvas com rolagem; `show(results)` redesenha tudo."""

    def __init__(self, parent, on_fix: Callable[[str], None]) -> None:
        super().__init__(parent, bg=COLORS["background"], highlightthickness=1,
                         highlightbackground=COLORS["border"])
        self._on_fix = on_fix
        self.canvas = tk.Canvas(self, bg=COLORS["background"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                  style="Pcx.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=COLORS["background"], padx=SPACE[2], pady=SPACE[1])
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        # A roda do mouse rola a lista so com o ponteiro em cima dela.
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))
        # Fechar com Esc com o ponteiro em cima nao gera <Leave>: solta aqui tambem.
        self.canvas.bind("<Destroy>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))
        self.fix_buttons: list[tk.Button] = []

    def _wheel(self, event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def show(self, results: list[CheckResult]) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        self.fix_buttons = []
        for group in GROUPS:
            items = [r for r in results if r.group == group]
            if not items:
                continue
            label(self.inner, group, font="body_bold", color="text_muted", anchor="w").pack(
                fill="x", pady=(SPACE[2], SPACE[0])
            )
            for result in items:
                self._row(result)
        self.canvas.yview_moveto(0)

    def _row(self, result: CheckResult) -> None:
        row = tk.Frame(self.inner, bg=COLORS["surface"], padx=SPACE[2], pady=SPACE[1] + 2)
        row.pack(fill="x", pady=(0, SPACE[1]))
        top = tk.Frame(row, bg=COLORS["surface"])
        top.pack(fill="x")
        dot = tk.Canvas(top, width=DOT, height=DOT, bg=COLORS["surface"], highlightthickness=0)
        dot.create_oval(1, 1, DOT - 1, DOT - 1, fill=COLORS[STATUS_COLORS[result.status]], outline="")
        dot.pack(side="left", padx=(0, SPACE[1]))
        label(top, result.title, font="body_bold", bg=COLORS["surface"], anchor="w").pack(side="left")
        # Situacao tambem em texto: a cor nao e o unico sinal.
        tk.Label(top, text=STATUS_TEXT[result.status], font=FONTS["small"], bg=COLORS["surface"],
                 fg=COLORS[STATUS_COLORS[result.status]]).pack(side="right")
        label(row, result.detail, font="small", color="text_muted", bg=COLORS["surface"], anchor="w",
              justify="left", wraplength=WRAP).pack(fill="x", pady=(SPACE[0], 0))
        if result.fix is not None:
            button = secondary_button(row, FIX_TEXT[result.fix], lambda fix=result.fix: self._on_fix(fix))
            button.pack(anchor="w", pady=(SPACE[1], 0))
            self.fix_buttons.append(button)
