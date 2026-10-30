import threading

import pytest

from pcx_agent.auth.pairing import PairError, PairingService
from pcx_agent.auth.passwords import PasswordService
from pcx_agent.auth.ratelimit import RateLimiter
from pcx_agent.storage.db import Database

DAY = 86400.0


class Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "pcx.db")
    passwords = PasswordService(db)
    passwords.set_password("segredo-123")
    mono = Clock()
    wall = Clock(1_000_000.0)
    limiter = RateLimiter(clock=mono)
    service = PairingService(db, passwords, limiter, clock=mono, now=wall)
    yield service, db, mono, wall
    db.close()


def pair_pw(service, ip="10.0.0.1", name="Moto G"):
    return service.pair(name, password="segredo-123", client_ip=ip)


def error_of(callable_):
    with pytest.raises(PairError) as info:
        callable_()
    return info.value


def test_pair_with_password_returns_token_and_stores_only_hash(env):
    service, db, _, _ = env
    result = pair_pw(service)
    assert result.token and result.device_id
    for row in db.query("SELECT * FROM devices"):
        assert result.token not in [str(value) for value in tuple(row)]


def test_pair_with_code_is_single_use(env):
    service, *_ = env
    code = service.new_code()
    service.pair("Moto G", code=code, client_ip="10.0.0.1")
    err = error_of(lambda: service.pair("Moto G", code=code, client_ip="10.0.0.1"))
    assert err.kind == "code_invalid_or_expired"


def test_new_code_invalidates_previous(env):
    service, *_ = env
    old = service.new_code()
    service.new_code()
    err = error_of(lambda: service.pair("Moto G", code=old, client_ip="10.0.0.1"))
    assert err.kind == "code_invalid_or_expired"


def test_code_expires_after_300s(env):
    service, _, mono, _ = env
    code = service.new_code()
    mono.now += 301
    err = error_of(lambda: service.pair("Moto G", code=code, client_ip="10.0.0.1"))
    assert err.kind == "code_invalid_or_expired"


def test_wrong_password_reports_attempts_left(env):
    service, *_ = env
    kinds = []
    for _ in range(2):
        err = error_of(lambda: service.pair("Moto G", password="errada-123", client_ip="9.9.9.9"))
        kinds.append((err.kind, err.attempts_left))
    assert kinds == [("bad_credentials", 4), ("bad_credentials", 3)]


def test_sixth_attempt_is_rate_limited_with_retry_after(env):
    service, *_ = env
    for _ in range(5):
        error_of(lambda: service.pair("Moto G", password="errada-123", client_ip="9.9.9.9"))
    err = error_of(lambda: pair_pw(service, ip="9.9.9.9"))
    assert err.kind == "rate_limited"
    assert err.retry_after is not None and 59 <= err.retry_after <= 60


def test_success_resets_failures(env):
    service, *_ = env
    for _ in range(3):
        error_of(lambda: service.pair("Moto G", password="errada-123", client_ip="9.9.9.9"))
    pair_pw(service, ip="9.9.9.9")
    err = error_of(lambda: service.pair("Moto G", password="errada-123", client_ip="9.9.9.9"))
    assert err.attempts_left == 4


def test_authenticate_valid_and_unknown_token(env):
    service, *_ = env
    result = pair_pw(service, name="Moto G")
    device = service.authenticate(result.token)
    assert device is not None and device.id == result.device_id and device.name == "Moto G"
    assert service.authenticate("token-inexistente") is None
    assert service.authenticate("") is None


def test_token_expires_30_days_after_last_use(env):
    service, _, _, wall = env
    token = pair_pw(service).token
    wall.now += 30 * DAY + 1
    assert service.authenticate(token) is None


def test_use_renews_expiry(env):
    service, _, _, wall = env
    token = pair_pw(service).token
    wall.now += 20 * DAY
    assert service.authenticate(token) is not None
    wall.now += 20 * DAY
    assert service.authenticate(token) is not None


def test_revoke_makes_token_invalid(env):
    service, *_ = env
    result = pair_pw(service)
    assert service.revoke(result.device_id) is True
    assert service.authenticate(result.token) is None
    assert service.revoke(result.device_id) is False


def test_revoke_all_and_list_devices(env):
    service, *_ = env
    first = pair_pw(service, name="A")
    second = pair_pw(service, name="B")
    assert {d.name for d in service.list_devices()} == {"A", "B"}
    service.revoke_all()
    assert service.list_devices() == []
    assert service.authenticate(first.token) is None
    assert service.authenticate(second.token) is None


def test_concurrent_pair_same_code_only_one_wins(env):
    service, *_ = env
    code = service.new_code()
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt(n: int) -> None:
        try:
            service.pair(f"Aparelho {n}", code=code, client_ip=f"10.0.0.{n}")
            result = "ok"
        except PairError as err:
            result = err.kind
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 1
    assert len(service.list_devices()) == 1


@pytest.mark.parametrize("name", ["", "   ", "x" * 65, "a\x00b", "linha\nquebrada"])
def test_device_name_validation(env, name):
    service, *_ = env
    err = error_of(lambda: service.pair(name, password="segredo-123", client_ip="10.0.0.1"))
    assert err.kind == "invalid_name"


def test_invalid_name_does_not_count_as_failed_attempt(env):
    service, *_ = env
    for _ in range(6):
        error_of(lambda: service.pair("", password="segredo-123", client_ip="10.0.0.1"))
    assert pair_pw(service).token
