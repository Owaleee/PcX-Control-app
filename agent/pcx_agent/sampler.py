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
        # Os eventos nascem em run(): cada restart do servidor roda num laco de eventos novo,
        # e um asyncio.Event fica preso ao laco em que foi usado pela primeira vez.
        self._stop: asyncio.Event | None = None
        self._nudge: asyncio.Event | None = None
        self.latest: Snapshot | None = None
        self.latest_at: float | None = None  # relogio do Sampler na ultima leitura boa
        # Chamado depois de publicar uma leitura em que o provider registrou uma falha.
        self.on_sensor_failure: Callable[[], None] | None = None

    def reading_age(self) -> float | None:
        """Segundos desde a ultima leitura boa; None se ainda nao houve nenhuma."""
        return None if self.latest_at is None else self._clock() - self.latest_at

    def current_interval(self) -> float:
        return self._active if self._has_active() else self._idle

    async def tick(self) -> None:
        try:
            snapshot = await asyncio.to_thread(self._provider.read)
        except Exception:
            logger.exception("Falha ao ler os sensores; mantendo a ultima leitura")
            return
        self.latest = snapshot
        self.latest_at = self._clock()
        self._notify_failure()
        self._accumulate(snapshot)
        if self.on_snapshot is not None and self._has_active():
            self.on_snapshot(snapshot)
        await self._maybe_flush()

    def _notify_failure(self) -> None:
        take = getattr(self._provider, "take_failure", None)
        callback = self.on_sensor_failure
        if take is None or callback is None:
            return
        try:
            if take():
                callback()
        except Exception:
            logger.debug("Aviso de falha dos sensores falhou", exc_info=True)

    def _accumulate(self, snapshot: Snapshot) -> None:
        for metric, value in snapshot.metrics().items():
            entry = self._acc.setdefault(metric, [0.0, 0.0, value])
            entry[0] += value
            entry[1] += 1
            entry[2] = max(entry[2], value)

    async def _maybe_flush(self) -> None:
        now = self._clock()
        if now - self._last_flush < self._flush_interval:
            return
        ts = self._wall()
        rows = [(metric, total / count, peak) for metric, (total, count, peak) in self._acc.items()]
        self._acc.clear()
        self._last_flush = now
        prune = now - self._last_prune >= PRUNE_INTERVAL_S
        if prune:
            self._last_prune = now
        try:
            # O SQLite (commit + fsync) roda em outra thread: nunca trava o laco de eventos.
            await asyncio.to_thread(self._write, ts, rows, prune)
        except Exception:
            logger.exception("Falha ao gravar o historico")

    def _write(self, ts: float, rows: list[tuple[str, float, float]], prune: bool) -> None:
        if rows:
            self._history.record_many(ts, rows)
        if prune:
            self._history.prune(ts)

    async def run(self) -> None:
        stop = self._stop = asyncio.Event()
        nudge = self._nudge = asyncio.Event()
        while not stop.is_set():
            nudge.clear()
            await self.tick()
            try:
                await asyncio.wait_for(nudge.wait(), timeout=self.current_interval())
            except TimeoutError:
                pass

    def nudge(self) -> None:
        """Acorda o laco para ler agora (por exemplo, quando uma sessao comeca)."""
        if self._nudge is not None:
            self._nudge.set()

    def stop(self) -> None:
        """Para o laco em andamento; sem laco rodando nao faz nada."""
        if self._stop is not None:
            self._stop.set()
        if self._nudge is not None:
            self._nudge.set()
