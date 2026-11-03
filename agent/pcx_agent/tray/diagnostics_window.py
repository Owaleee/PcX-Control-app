"""Janela "Verificar conexao": roda o diagnostico em segundo plano e mostra o que fazer."""

import logging
from concurrent.futures import Future, ThreadPoolExecutor

from pcx_agent.diagnostics.model import CheckResult
from pcx_agent.tray import texts
from pcx_agent.tray.diagnostics_rows import ResultList
from pcx_agent.tray.theme import COLORS, GAP, SPACE
from pcx_agent.tray.widgets import (
    BaseWindow,
    button_row,
    heading,
    label,
    primary_button,
    secondary_button,
)

POLL_MS = 150
logger = logging.getLogger("pcx_agent.tray")
# O diagnostico chama o PowerShell (alguns segundos): nunca na thread da interface.
_RUNS = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pcx-diagnostico")


def summary(results: list[CheckResult]) -> tuple[str, str]:
    """(texto, cor) do resumo no topo da lista."""
    problems = sum(r.status == "problema" for r in results)
    warnings = sum(r.status == "atencao" for r in results)
    if problems:
        return texts.DIAG_SUMMARY_PROBLEMS.format(n=problems), "danger"
    if warnings:
        return texts.DIAG_SUMMARY_WARNINGS.format(n=warnings), "warning"
    return texts.DIAG_SUMMARY_OK, "ok"


class DiagnosticsWindow(BaseWindow):
    size_key = "diagnostics"
    title_text = texts.TITLE_DIAGNOSTICS

    def __init__(self, root, controller) -> None:
        super().__init__(root, controller)
        heading(self.body, texts.DIAG_HEADING, texts.DIAG_SUBTITLE).pack(fill="x")
        self.status = label(self.body, texts.DIAG_RUNNING, font="body_bold", anchor="w")
        self.status.pack(fill="x", pady=(GAP, SPACE[1]))
        self.results_list = ResultList(self.body, self._fix)
        self.results_list.pack(fill="both", expand=True)
        row = button_row(self.body)
        self.copy_button = secondary_button(row, texts.DIAG_COPY, self.copy_report)
        self.copy_button.pack(side="left")
        primary_button(row, texts.CLOSE, self.close).pack(side="right")
        self.again_button = secondary_button(row, texts.DIAG_AGAIN, self.run)
        self.again_button.pack(side="right", padx=(0, SPACE[1]))
        self.results: list[CheckResult] = []
        self._running: Future | None = None
        self._rerun_on_focus = False
        self.bind("<FocusIn>", self._focus_back)
        self.run()

    def run(self) -> None:
        if self._running is not None and not self._running.done():
            return  # um diagnostico por vez
        self.status.configure(text=texts.DIAG_RUNNING, fg=COLORS["text"])
        self.again_button.configure(state="disabled")
        self._running = _RUNS.submit(self.controller.run_diagnostics)
        self.after(POLL_MS, self._poll, self._running)

    def _poll(self, running: Future) -> None:
        if not self.winfo_exists() or running is not self._running:
            return
        if not running.done():
            self.after(POLL_MS, self._poll, running)
            return
        self.again_button.configure(state="normal")
        try:
            self.results = running.result()
        except Exception:
            logger.exception("Diagnostico falhou")
            self.status.configure(text=texts.DIAG_SUMMARY_PROBLEMS.format(n=1), fg=COLORS["danger"])
            return
        text, color = summary(self.results)
        self.status.configure(text=text, fg=COLORS[color])
        self.results_list.show(self.results)

    def _fix(self, fix: str) -> None:
        self.controller.apply_fix(fix)
        self._rerun_on_focus = True  # ao voltar das Configuracoes ou do pedido de administrador

    def _focus_back(self, event) -> None:
        if event.widget is self and self._rerun_on_focus:
            self._rerun_on_focus = False
            self.run()

    def copy_report(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.controller.diagnostics_report(self.results))
        self.status.configure(text=texts.DIAG_COPIED, fg=COLORS["ok"])

    def primary_action(self) -> None:
        self.close()

    def on_reopen(self) -> None:
        self.run()
