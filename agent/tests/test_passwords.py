import pytest

from pcx_agent.auth.passwords import PasswordService, hash_password, verify_password
from pcx_agent.storage.db import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "pcx.db")
    yield database
    database.close()


def test_hash_is_not_plaintext_and_salted():
    first = hash_password("segredo-123")
    second = hash_password("segredo-123")
    assert first != second
    assert "segredo-123" not in first
    assert first.startswith("scrypt$")


def test_verify_accepts_right_and_rejects_wrong():
    stored = hash_password("segredo-123")
    assert verify_password("segredo-123", stored) is True
    assert verify_password("segredo-124", stored) is False


@pytest.mark.parametrize("stored", ["", "lixo", "scrypt$1$2", "scrypt$x$y$z$a$b", "md5$a$b"])
def test_verify_rejects_malformed_stored_value(stored):
    assert verify_password("segredo-123", stored) is False


def test_set_password_rejects_short(db):
    with pytest.raises(ValueError):
        PasswordService(db).set_password("1234567")


def test_service_without_password_never_verifies(db):
    service = PasswordService(db)
    assert service.is_set() is False
    assert service.verify("qualquer-coisa") is False
    assert service.verify("") is False


def test_service_set_and_verify(db):
    service = PasswordService(db)
    service.set_password("segredo-123")
    assert service.is_set() is True
    assert service.verify("segredo-123") is True
    assert service.verify("outra-senha") is False


def test_password_stored_only_as_hash(db):
    PasswordService(db).set_password("segredo-123")
    values = [row["value"] for row in db.query("SELECT value FROM settings")]
    assert all("segredo-123" not in value for value in values)


def test_scrypt_concurrency_is_bounded(db, monkeypatch):
    import threading
    import time

    import pcx_agent.auth.passwords as passwords_module

    service = PasswordService(db)
    service.set_password("segredo-123")
    state = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def slow_verify(password, stored):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return False

    monkeypatch.setattr(passwords_module, "verify_password", slow_verify)
    threads = [threading.Thread(target=service.verify, args=("x",)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert state["peak"] <= 2
