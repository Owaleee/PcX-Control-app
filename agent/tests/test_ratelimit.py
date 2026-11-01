from pcx_agent.auth.ratelimit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make() -> tuple[RateLimiter, Clock]:
    clock = Clock()
    return RateLimiter(clock=clock), clock


def test_blocks_after_five_failures():
    limiter, _ = make()
    for _ in range(5):
        limiter.record_failure("1.1.1.1")
    remaining = limiter.blocked_for("1.1.1.1")
    assert remaining is not None
    assert 59 <= remaining <= 60


def test_remaining_attempts_counts_down():
    limiter, _ = make()
    assert [limiter.record_failure("a") for _ in range(5)] == [4, 3, 2, 1, 0]


def test_not_blocked_before_limit():
    limiter, _ = make()
    for _ in range(4):
        limiter.record_failure("a")
    assert limiter.blocked_for("a") is None


def test_block_expires():
    limiter, clock = make()
    for _ in range(5):
        limiter.record_failure("a")
    clock.now += 61
    assert limiter.blocked_for("a") is None


def test_failures_outside_window_are_forgotten():
    limiter, clock = make()
    for _ in range(4):
        limiter.record_failure("a")
    clock.now += 61
    assert limiter.record_failure("a") == 4


def test_keys_are_independent():
    limiter, _ = make()
    for _ in range(5):
        limiter.record_failure("a")
    assert limiter.blocked_for("b") is None
    assert limiter.record_failure("b") == 4


def test_reset_clears_failures():
    limiter, _ = make()
    for _ in range(3):
        limiter.record_failure("a")
    limiter.reset("a")
    assert limiter.record_failure("a") == 4


def test_begin_attempt_counts_up_front_and_reports_remaining():
    limiter, _ = make()
    assert [limiter.begin_attempt("a") for _ in range(5)] == [
        (None, 4), (None, 3), (None, 2), (None, 1), (None, 0),
    ]
    retry, left = limiter.begin_attempt("a")
    assert retry is not None and 59 <= retry <= 60 and left == 0


def test_begin_attempt_success_reset_clears_the_reservation():
    limiter, _ = make()
    for _ in range(3):
        limiter.begin_attempt("a")
    limiter.reset("a")
    assert limiter.begin_attempt("a") == (None, 4)


def test_undo_attempt_gives_the_slot_back():
    limiter, _ = make()
    for _ in range(4):
        limiter.begin_attempt("a")
    limiter.undo_attempt("a")
    assert limiter.begin_attempt("a") == (None, 1)


def test_undo_attempt_without_attempts_is_harmless():
    limiter, _ = make()
    limiter.undo_attempt("nada")
    assert limiter.blocked_for("nada") is None
