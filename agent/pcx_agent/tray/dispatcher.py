"""Leva chamadas de outras threads (servidor, pystray) para a thread do tkinter."""

import queue
import tkinter as tk
from collections.abc import Callable

POLL_MS = 50


class Dispatcher:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._calls: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._root.after(POLL_MS, self._drain)

    def call(self, fn: Callable[[], None]) -> None:
        """Pode ser chamado de qualquer thread; `fn` roda na thread do tkinter."""
        self._calls.put(fn)

    def _drain(self) -> None:
        while True:
            try:
                fn = self._calls.get_nowait()
            except queue.Empty:
                break
            fn()
        self._root.after(POLL_MS, self._drain)
