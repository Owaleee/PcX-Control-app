"""Limite de tentativas por chave (por exemplo, o IP do cliente)."""

import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        max_failures: int = 5,
        window_s: float = 60.0,
        block_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_failures
        self._window = window_s
        self._block = block_s
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def blocked_for(self, key: str) -> float | None:
        """Segundos restantes de bloqueio, ou None se a chave nao esta bloqueada."""
        with self._lock:
            until = self._blocked_until.get(key)
            if until is None:
                return None
            remaining = until - self._clock()
            if remaining <= 0:
                del self._blocked_until[key]
                return None
            return remaining

    def _record_locked(self, key: str, now: float) -> int:
        window = self._failures.setdefault(key, deque())
        while window and now - window[0] >= self._window:
            window.popleft()
        window.append(now)
        remaining = max(0, self._max - len(window))
        if len(window) >= self._max:
            self._blocked_until[key] = now + self._block
            window.clear()
        return remaining

    def record_failure(self, key: str) -> int:
        """Registra uma falha e devolve quantas tentativas restam antes do bloqueio."""
        with self._lock:
            return self._record_locked(key, self._clock())

    def begin_attempt(self, key: str) -> tuple[float | None, int]:
        """Reserva uma tentativa de forma atomica, ANTES de verificar a credencial.

        Devolve (segundos_de_bloqueio, 0) se a chave esta bloqueada; senao conta a tentativa
        como falha provisoria e devolve (None, tentativas_restantes). Quem acertar chama
        `reset`. Assim, pedidos simultaneos nao passam do limite.
        """
        with self._lock:
            now = self._clock()
            until = self._blocked_until.get(key)
            if until is not None:
                if until > now:
                    return until - now, 0
                del self._blocked_until[key]
            return None, self._record_locked(key, now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._blocked_until.pop(key, None)
