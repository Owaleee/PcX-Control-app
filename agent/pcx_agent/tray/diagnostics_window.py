"""Janela "Verificar conexao": roda o diagnostico em segundo plano e mostra o que fazer."""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future

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
from pcx_agent.winsys import folders

POLL_MS = 150
logger = logging.getLogger("pcx_agent.tray")


def in_background(work: Callable[[], object]) -> Future:
    """Roda fora da thread da interface (o diagnostico chama o PowerShell por alguns segundos).

    Thread daemon: sair pela bandeja no meio de um diagnostico nao espera o PowerShell terminar.
    """
    future: Future = Future()

    def run() -> None:
        try:
            future.set_result(work())
        except BaseException as exc:  # noqa: BLE001 - entregue a quem consulta o resultado
            future.set_exception(exc)

    threading.Thread(target=run, name="pcx-diagnostico", daemon=True).start()
    return future


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
        self.save_button = secondary_button(row, texts.DIAG_SAVE_PACKAGE, self.save_package)
        self.save_button.pack(side="left")
        primary_button(row, texts.CLOSE, self.close).pack(side="right")
        self.again_button = secondary_button(row, texts.DIAG_AGAIN, self.run)
        self.again_button.pack(side="right", padx=(0, SPACE[1]))
        self.results: list[CheckResult] = []
        self._running: Future | None = None
        self._rerun_on_focus = False
        self._fix_message: str | None = None
        self.bind("<FocusIn>", self._focus_back)
        self.run()

    def run(self) -> None:
        if self._running is not None and not self._running.done():
            return  # um diagnostico por vez
        self.status.configure(text=texts.DIAG_RUNNING, fg=COLORS["text"])
        self.again_button.configure(state="disabled")
        self._running = in_background(self.controller.run_diagnostics)
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
        if self._fix_message:  # o aviso da correcao ocupa o lugar do resumo uma vez
            text, color, self._fix_message = self._fix_message, "ok", None
        self.status.configure(text=text, fg=COLORS[color])
        self.results_list.show(self.results)

    def _fix(self, fix: str) -> None:
        if fix == "copiar_caminho":  # area de transferencia do Tk: so na thread da interface
            self.clipboard_clear()
            self.clipboard_append(self.controller.program_path())
            self.status.configure(text=texts.DIAG_PATH_COPIED, fg=COLORS["ok"])
            return
        if fix == "salvar_pacote":
            self.save_package()
            return
        # O pedido de administrador segura a chamada: fora da thread da interface.
        done = in_background(lambda: self.controller.apply_fix(fix))
        if fix == "abrir_rede":
            self._rerun_on_focus = True  # ao voltar das Configuracoes de rede
        else:
            self.after(POLL_MS, self._after_fix, done)  # a correcao terminou: verifica de novo

    def _after_fix(self, done: Future) -> None:
        if not self.winfo_exists():
            return
        if not done.done():
            self.after(POLL_MS, self._after_fix, done)
            return
        self.run()
        message = getattr(self.controller, "last_fix_message", None)
        if message:
            self.controller.last_fix_message = None
            self._fix_message = message

    def _focus_back(self, event) -> None:
        if event.widget is self and self._rerun_on_focus:
            self._rerun_on_focus = False
            self.run()

    def save_package(self) -> None:
        """Monta o zip fora da thread da interface; depois mostra a pasta e verifica de novo."""
        self.save_button.configure(state="disabled")
        self.status.configure(text=texts.DIAG_SAVING, fg=COLORS["text"])
        saving = in_background(lambda: self.controller.save_support_package(self.results))
        self.after(POLL_MS, self._after_save, saving)

    def _after_save(self, saving: Future) -> None:
        if not self.winfo_exists():
            return
        if not saving.done():
            self.after(POLL_MS, self._after_save, saving)
            return
        self.save_button.configure(state="normal")
        try:
            path = saving.result()
        except Exception:
            logger.exception("Pacote de suporte falhou")
            self.status.configure(text=texts.DIAG_PACKAGE_FAILED, fg=COLORS["danger"])
            return
        folders.reveal(path)
        self._fix_message = texts.DIAG_PACKAGE_SAVED.format(nome=path.name)
        self.run()  # o aviso de fechamento inesperado some

    def primary_action(self) -> None:
        self.close()

    def on_reopen(self) -> None:
        self.run()
