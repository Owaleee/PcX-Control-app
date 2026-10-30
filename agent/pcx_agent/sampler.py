"""Laco unico de coleta: le os sensores, alimenta o historico e a sessao ativa."""

import asyncio
import logging
import time
from collections.abc import Callable

from pcx_agent.sensors.base import SensorProvider, Snapshot
from pcx_agent.storage.history import HistoryStore

logger = logging.getLogger("pcx_agent.sampler")
PRUNE_INTERVAL_S = 3600.0


class Sampler:
    def __init__(
        self,
        provider: SensorProvider,
        history: HistoryStore,
        has_active_session: Callable[[], bool],
        on_snapshot: Callable[[Snapshot], None] | None = None,
        idle_interval: float = 5.0,
        active_interval: float = 1.0,
        flush_interval: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
    ) -> None:
        self._provider = provider
        self._history = history
        self._has_active = has_active_session
        self.on_snapshot = on_snapshot
        self._idle = idle_interval
        self._active = active_interval
        self._flush_interval = flush_interval
        self._clock = clock
        self._wall = wall
        self._acc: dict[str, list[float]] = {}  # metrica -> [soma, quantidade, maximo]
        self._last_flush = clock()
        self._last_prune = clock()
        self._stop = asyncio.Event()
        self._nudge = asyncio.Event()
        self.latest: Snapshot | None = None

    def current_interval(self) -> float:
        return self._active if self._has_active() else self._idle

    async def tick(self) -> None:
        try:
            snapshot = await asyncio.to_thread(self._provider.read)
        except Exception:
            logger.exception("Falha ao ler os sensores; mantendo a ultima leitura")
            return
        self.latest = snapshot
        self._accumulate(snapshot)
        if self.on_snapshot is not None and self._has_active():
            self.on_snapshot(snapshot)
        self._maybe_flush()

    def _accumulate(self, snapshot: Snapshot) -> None:
        for metric, value in snapshot.metrics().items():
            entry = self._acc.setdefault(metric, [0.0, 0.0, value])
            entry[0] += value
            entry[1] += 1
            entry[2] = max(entry[2], value)

    def _maybe_flush(self) -> None:
        now = self._clock()
        if now - self._last_flush < self._flush_interval:
            return
        ts = self._wall()
        try:
            for metric, (total, count, peak) in self._acc.items():
                self._history.record(ts, metric, total / count, peak)
            if now - self._last_prune >= PRUNE_INTERVAL_S:
                self._history.prune(ts)
                self._last_prune = now
        except Exception:
            logger.exception("Falha ao gravar o historico")
        self._acc.clear()
        self._last_flush = now

    async def run(self) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            self._nudge.clear()
            await self.tick()
            try:
                await asyncio.wait_for(self._nudge.wait(), timeout=self.current_interval())
            except TimeoutError:
                pass

    def nudge(self) -> None:
        """Acorda o laco para ler agora (por exemplo, quando uma sessao comeca)."""
        self._nudge.set()

    def stop(self) -> None:
        self._stop.set()
        self._nudge.set()
