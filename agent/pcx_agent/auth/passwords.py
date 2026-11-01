"""Senha do PC: guardada apenas como hash scrypt com salt."""

import base64
import hashlib
import hmac
import secrets
import threading

from pcx_agent.storage.db import Database

MIN_LENGTH = 8
SETTING_KEY = "password_hash"
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32
MAXMEM = 128 * 1024 * 1024
MAX_PARALLEL_SCRYPT = 2


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=KEY_BYTES, maxmem=MAXMEM
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    parts = [
        "scrypt",
        str(SCRYPT_N),
        str(SCRYPT_R),
        str(SCRYPT_P),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(key).decode("ascii"),
    ]
    return "$".join(parts)


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(key_b64, validate=True)
        actual = _derive(password, salt, int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


class PasswordService:
    def __init__(self, db: Database) -> None:
        self._db = db
        # Cada scrypt aloca ~32 MiB: limita quantos rodam ao mesmo tempo.
        self._gate = threading.BoundedSemaphore(MAX_PARALLEL_SCRYPT)

    def is_set(self) -> bool:
        return self._db.get_setting(SETTING_KEY) is not None

    def set_password(self, password: str) -> None:
        if len(password) < MIN_LENGTH:
            raise ValueError(f"A senha precisa ter pelo menos {MIN_LENGTH} caracteres.")
        self._db.set_setting(SETTING_KEY, hash_password(password))

    def verify(self, password: str) -> bool:
        stored = self._db.get_setting(SETTING_KEY)
        if stored is None:
            return False
        with self._gate:
            return verify_password(password, stored)
