"""Diagnostico automatico: roda as verificacoes em segundo plano e alimenta o monitor do alerta.

Nao toca em Tk nem em pystray: quem usa entrega `schedule` (thread da interface), `background`
(thread solta) e `ui` (volta para a thread da interface). O monitor nao tem trava, entao
`monitor.update` so roda dentro de `ui`.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future

from pcx_agent.diagnostics.model import CheckResult
from pcx_agent.diagnostics.monitor import DiagnosticsMonitor
from pcx_agent.diagnostics.runner import ALL_CHECKS, QUICK_CHECKS

logger = logging.getLogger("pcx_agent.tray")


class AlertScheduler:
    def __init__(
        self,
        run: Callable[[set[str] | None], list[CheckResult]],
        monitor: DiagnosticsMonitor,
        schedule: Callable[[int, Callable[[], None]], None],
        background: Callable[[Callable[[], object]], Future],
        ui: Callable[[Callable[[], None]], None],
        first_delay_ms: int = 10_000,
        interval_ms: int = 300_000,
        maintenance: Callable[[], None] | None = None,
    ) -> None:
        self._run = run
        self._monitor = monitor
        self._schedule = schedule
        self._background = background
        self._ui = ui
        self._first_delay_ms = first_delay_ms
        self._interval_ms = interval_ms
        self._maintenance = maintenance
        self._lock = threading.Lock()
        self._running = False
        self._pending: tuple[set[str] | None] | None = None  # so o pedido mais recente

    def start(self) -> None:
        """Chamar na thread da interface: `schedule` e o `after` do Tk."""
        self._schedule(self._first_delay_ms, self._first)

    def _first(self) -> None:
        self._schedule(self._interval_ms, self._tick)
        self.trigger(None)

    def _tick(self) -> None:
        self._schedule(self._interval_ms, self._tick)
        self.trigger(set(QUICK_CHECKS))

    def trigger(self, ids: set[str] | None) -> None:
        """Pede uma rodada (pode vir de qualquer thread). Sem fila: guarda so o ultimo pedido."""
        with self._lock:
            if self._running:
                self._pending = (None if ids is None else set(ids),)
                return
            self._running = True
        self._launch(ids)

    def feed(self, results: list[CheckResult], ran: set[str]) -> None:
        """Resultado de uma rodada feita por outro caminho (a janela): alimenta o monitor."""
        self._ui(lambda: self._monitor.update(results, set(ran)))

    def _launch(self, ids: set[str] | None) -> None:
        self._background(lambda: self._work(ids))

    def _work(self, ids: set[str] | None) -> None:
        try:
            results = self._run(ids)
            ran = set(ALL_CHECKS) if ids is None else set(ids)
            self._ui(lambda: self._monitor.update(results, ran))
            if self._maintenance is not None:
                self._maintenance()
        except Exception:
            logger.exception("Diagnóstico automático falhou")
        finally:
            with self._lock:
                pending, self._pending = self._pending, None
                self._running = pending is not None
            if pending is not None:
                self._launch(pending[0])
