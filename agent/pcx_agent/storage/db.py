"""SQLite: configuracoes, aparelhos pareados e historico."""

import socket
import sqlite3
import threading
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    last_used_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    ts REAL NOT NULL,
    metric TEXT NOT NULL,
    avg REAL NOT NULL,
    max REAL NOT NULL,
    PRIMARY KEY (ts, metric)
);
"""


class Database:
    """Conexao unica protegida por lock, segura para varias threads."""

    def __init__(self, path: Path | str) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")  # seguro em WAL, sem fsync a cada commit
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        if self.get_setting("agent_id") is None:
            self.set_setting("agent_id", str(uuid.uuid4()))
        if self.get_setting("agent_name") is None:
            self.set_setting("agent_name", socket.gethostname() or "PC")

    @property
    def agent_id(self) -> str:
        return self.get_setting("agent_id") or ""

    @property
    def agent_name(self) -> str:
        return self.get_setting("agent_name") or "PC"

    def get_setting(self, key: str) -> str | None:
        rows = self.query("SELECT value FROM settings WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def set_setting(self, key: str, value: str) -> None:
        self.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor.rowcount

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> None:
        """Varias linhas numa unica transacao (um commit so)."""
        if not rows:
            return
        with self._lock:
            self._conn.executemany(sql, rows)
            self._conn.commit()

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
