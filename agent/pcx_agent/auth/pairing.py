"""Pareamento de celulares, tokens de aparelho e sessoes por token."""

import hashlib
import hmac
import secrets
import threading
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pcx_agent.auth.passwords import PasswordService
from pcx_agent.auth.ratelimit import RateLimiter
from pcx_agent.storage.db import Database

ErrorKind = Literal["rate_limited", "bad_credentials", "code_invalid_or_expired", "invalid_name"]
MAX_NAME_LENGTH = 64
RENEW_AFTER_S = 3600.0
GLOBAL_KEY = "*"
GLOBAL_MAX_FAILURES = 30


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    created_at: float
    last_used_at: float


@dataclass(frozen=True)
class PairResult:
    device_id: str
    token: str


class PairError(Exception):
    def __init__(
        self,
        kind: ErrorKind,
        retry_after: float | None = None,
        attempts_left: int | None = None,
    ) -> None:
        super().__init__(kind)
        self.kind = kind
        self.retry_after = retry_after
        self.attempts_left = attempts_left


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    has_control = any(unicodedata.category(char).startswith("C") for char in cleaned)
    if not cleaned or len(cleaned) > MAX_NAME_LENGTH or has_control:
        raise PairError("invalid_name")
    return cleaned


class PairingService:
    def __init__(
        self,
        db: Database,
        passwords: PasswordService,
        limiter: RateLimiter,
        code_ttl_s: float = 300.0,
        token_ttl_s: float = 30 * 86400.0,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], float] = time.time,
        global_limiter: RateLimiter | None = None,
    ) -> None:
        self._db = db
        self._passwords = passwords
        self._limiter = limiter
        # Teto para a rede toda: impede varrer senhas trocando de IP.
        self._global = global_limiter or RateLimiter(
            max_failures=GLOBAL_MAX_FAILURES, window_s=60.0, block_s=60.0, clock=clock
        )
        self._code_ttl = code_ttl_s
        self._token_ttl = token_ttl_s
        self._clock = clock
        self._now = now
        self._code: tuple[str, float] | None = None
        self._lock = threading.Lock()
        self.on_revoke: Callable[[str | None], None] | None = None
        self.on_pair: Callable[[Device], None] | None = None

    @property
    def code_ttl_s(self) -> float:
        return self._code_ttl

    def new_code(self) -> str:
        code = secrets.token_urlsafe(16)
        with self._lock:
            self._code = (code, self._clock() + self._code_ttl)
        return code

    def _consume_code(self, candidate: str) -> bool:
        with self._lock:
            if self._code is None:
                return False
            code, expires_at = self._code
            if self._clock() > expires_at:
                self._code = None
                return False
            if not hmac.compare_digest(code.encode("utf-8"), candidate.encode("utf-8")):
                return False
            self._code = None
            return True

    def pair(
        self,
        device_name: str,
        *,
        code: str | None = None,
        password: str | None = None,
        client_ip: str,
    ) -> PairResult:
        name = _clean_name(device_name)
        if code is None:
            # Teto da rede so para senha: os codigos tem 128 bits e o dono ainda pareia pelo QR.
            # Conferido antes do limite do IP, para nao gastar as tentativas deste IP.
            global_wait = self._global.blocked_for(GLOBAL_KEY)
            if global_wait is not None:
                raise PairError("rate_limited", retry_after=global_wait)
        retry_after, left = self._limiter.begin_attempt(client_ip)
        if retry_after is not None:
            raise PairError("rate_limited", retry_after=retry_after)

        if code is not None:
            if not self._consume_code(code):
                raise PairError("code_invalid_or_expired")
        elif password is not None and self._passwords.verify(password):
            pass
        else:
            self._global.record_failure(GLOBAL_KEY)
            raise PairError("bad_credentials", attempts_left=left)

        self._limiter.reset(client_ip)
        result = self._create_device(name)
        if self.on_pair is not None:
            rows = self._db.query("SELECT * FROM devices WHERE id = ?", (result.device_id,))
            row = rows[0]
            self.on_pair(Device(row["id"], row["name"], row["created_at"], row["last_used_at"]))
        return result

    def _create_device(self, name: str) -> PairResult:
        device_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        now = self._now()
        self._db.execute(
            "INSERT INTO devices (id, name, token_hash, created_at, last_used_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (device_id, name, _hash_token(token), now, now),
        )
        return PairResult(device_id=device_id, token=token)

    def authenticate(self, token: str) -> Device | None:
        if not token:
            return None
        rows = self._db.query("SELECT * FROM devices WHERE token_hash = ?", (_hash_token(token),))
        if not rows:
            return None
        row = rows[0]
        now = self._now()
        if now - row["last_used_at"] > self._token_ttl:
            self._db.execute("DELETE FROM devices WHERE id = ?", (row["id"],))
            return None
        last_used = row["last_used_at"]
        if now - last_used >= RENEW_AFTER_S:  # evita um fsync por reconexao
            self._db.execute("UPDATE devices SET last_used_at = ? WHERE id = ?", (now, row["id"]))
            last_used = now
        return Device(row["id"], row["name"], row["created_at"], last_used)

    def revoke(self, device_id: str) -> bool:
        deleted = self._db.execute("DELETE FROM devices WHERE id = ?", (device_id,)) > 0
        if deleted and self.on_revoke is not None:
            self.on_revoke(device_id)
        return deleted

    def revoke_all(self) -> None:
        self._db.execute("DELETE FROM devices")
        if self.on_revoke is not None:
            self.on_revoke(None)

    def list_devices(self) -> list[Device]:
        rows = self._db.query("SELECT * FROM devices ORDER BY created_at, name")
        return [Device(r["id"], r["name"], r["created_at"], r["last_used_at"]) for r in rows]
