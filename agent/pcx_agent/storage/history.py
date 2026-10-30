"""Historico das metricas: media e maximo a cada 5 s, retencao de 24 h."""

from dataclasses import dataclass

from pcx_agent.storage.db import Database

VALID_RANGES: dict[str, float] = {"15m": 15 * 60.0, "1h": 3600.0, "24h": 86400.0}


@dataclass(frozen=True)
class HistoryPoint:
    t: float
    avg: float
    max: float


class HistoryStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, ts: float, metric: str, avg: float, max_: float) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO history (ts, metric, avg, max) VALUES (?, ?, ?, ?)",
            (ts, metric, avg, max_),
        )

    def record_many(self, ts: float, rows: list[tuple[str, float, float]]) -> None:
        """Grava varias metricas do mesmo instante em uma transacao: (metrica, media, maximo)."""
        self._db.executemany(
            "INSERT OR REPLACE INTO history (ts, metric, avg, max) VALUES (?, ?, ?, ?)",
            [(ts, metric, avg, peak) for metric, avg, peak in rows],
        )

    def query(self, metric: str, range_: str, now: float) -> list[HistoryPoint]:
        if range_ not in VALID_RANGES:
            raise ValueError(f"Intervalo invalido: {range_}")
        since = now - VALID_RANGES[range_]
        rows = self._db.query(
            "SELECT ts, avg, max FROM history WHERE metric = ? AND ts >= ? ORDER BY ts",
            (metric, since),
        )
        return [HistoryPoint(r["ts"], r["avg"], r["max"]) for r in rows]

    def prune(self, now: float, keep_s: float = 86400.0) -> int:
        return self._db.execute("DELETE FROM history WHERE ts < ?", (now - keep_s,))
