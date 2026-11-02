"""Leva chamadas de outras threads (servidor, pystray) para a thread do tkinter."""

import logging
import queue
import tkinter as tk
from collections.abc import Callable

POLL_MS = 50
logger = logging.getLogger("pcx_agent.tray")


class Dispatcher:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._calls: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        # Sem console (.exe), o erro de um botao ou timer sumiria: vai para o log.
        root.report_callback_exception = self._report
        self._root.after(POLL_MS, self._drain)

    def call(self, fn: Callable[[], None]) -> None:
        """Pode ser chamado de qualquer thread; `fn` roda na thread do tkinter."""
        self._calls.put(fn)

    @staticmethod
    def _report(kind, value, traceback) -> None:
        logger.error("Erro na interface", exc_info=(kind, value, traceback))

    def _drain(self) -> None:
        try:
            while True:
                try:
                    fn = self._calls.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn()
                except Exception:  # uma acao que falha nao pode travar as proximas
                    logger.exception("Falha numa ação da bandeja")
        finally:
            self._root.after(POLL_MS, self._drain)
