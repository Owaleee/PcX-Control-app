"""Monitor do alerta do diagnostico: quais verificacoes estao em alerta e quando avisar."""

import time
from collections.abc import Callable

from pcx_agent.diagnostics.model import CheckResult

ALERT_STATUSES = frozenset({"problema", "atencao"})
# A VPN e o antivirus de terceiros sao informativos: aparecem na janela do diagnostico, mas
# nunca acendem o alerta sozinhos.
ALERT_EXCLUDED = frozenset({"rede.vpn", "antivirus.terceiros"})

_SEVERITY = {"problema": 2, "atencao": 1}


class DiagnosticsMonitor:
    """Guarda o pior resultado por id e avisa no maximo uma vez a cada `notify_gap_s`."""

    def __init__(
        self,
        on_alert_change: Callable[[frozenset[str]], None],
        on_notify: Callable[[CheckResult], None],
        clock: Callable[[], float] = time.monotonic,
        notify_gap_s: float = 600.0,
    ) -> None:
        self._on_alert_change = on_alert_change
        self._on_notify = on_notify
        self._clock = clock
        self._gap = notify_gap_s
        self._worst: dict[str, CheckResult] = {}  # so ids em alerta
        self._pending: list[str] = []  # entraram no alerta e ainda nao foram avisados
        self._last_notify: float | None = None

    @property
    def alert_ids(self) -> frozenset[str]:
        return frozenset(self._worst)

    def update(self, results: list[CheckResult], ran: set[str]) -> None:
        """Substitui so os ids de `ran`; os demais ficam como estavam."""
        before = self.alert_ids
        touched = set(ran) | {r.id for r in results}
        for id_ in touched:
            self._worst.pop(id_, None)
        for r in results:
            if r.status not in ALERT_STATUSES or r.id in ALERT_EXCLUDED:
                continue
            current = self._worst.get(r.id)
            if current is None or _SEVERITY[r.status] > _SEVERITY[current.status]:
                self._worst[r.id] = r
        after = self.alert_ids
        # Avisa primeiro os problemas, depois as atencoes; no empate, pela ordem do id.
        waiting = {i for i in self._pending if i in after} | (after - before)
        self._pending = sorted(waiting, key=lambda i: (-_SEVERITY[self._worst[i].status], i))
        if after != before:
            self._on_alert_change(after)
        self._notify_next()

    def _notify_next(self) -> None:
        if not self._pending:
            return
        now = self._clock()
        if self._last_notify is not None and now - self._last_notify < self._gap:
            return
        id_ = self._pending.pop(0)
        self._last_notify = now
        self._on_notify(self._worst[id_])
