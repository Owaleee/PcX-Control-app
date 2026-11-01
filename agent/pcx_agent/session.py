"""Regra de sessao ativa unica: um celular por vez, com opcao de assumir."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


@dataclass
class ActiveSession:
    device_id: str
    device_name: str
    evict: Callable[[], None]
    on_revoke: Callable[[], None] | None = None


@dataclass(frozen=True)
class AcquireResult:
    status: Literal["granted", "busy"]
    active_device_name: str | None = None


class SessionManager:
    def __init__(self, timeout_s: float = 15.0, clock: Callable[[], float] = time.monotonic):
        self._timeout = timeout_s
        self._clock = clock
        self._lock = threading.Lock()
        self._session: ActiveSession | None = None
        self._last_seen = 0.0

    def _expire_locked(self) -> None:
        if self._session is not None and self._clock() - self._last_seen > self._timeout:
            self._session = None

    def acquire(self, session: ActiveSession, takeover: bool) -> AcquireResult:
        to_evict: ActiveSession | None = None
        with self._lock:
            self._expire_locked()
            current = self._session
            if current is not None and current.device_id != session.device_id:
                if not takeover:
                    return AcquireResult("busy", current.device_name)
                to_evict = current
            self._session = session
            self._last_seen = self._clock()
        if to_evict is not None:
            to_evict.evict()
        return AcquireResult("granted")

    def release(self, device_id: str, session: ActiveSession | None = None) -> None:
        """Libera a sessao do aparelho. Com `session`, so libera se for exatamente essa."""
        with self._lock:
            current = self._session
            if current is None or current.device_id != device_id:
                return
            if session is not None and current is not session:
                return
            self._session = None

    def revoke(self, device_id: str | None) -> None:
        """Encerra a sessao do aparelho revogado (None: qualquer aparelho) e avisa a conexao."""
        with self._lock:
            current = self._session
            if current is None or (device_id is not None and current.device_id != device_id):
                return
            self._session = None
        if current.on_revoke is not None:
            current.on_revoke()

    def touch(self, device_id: str) -> None:
        with self._lock:
            if self._session is not None and self._session.device_id == device_id:
                self._last_seen = self._clock()

    def active(self) -> ActiveSession | None:
        with self._lock:
            self._expire_locked()
            return self._session

    def has_active(self) -> bool:
        return self.active() is not None
