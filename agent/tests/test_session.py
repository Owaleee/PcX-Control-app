from pcx_agent.session import ActiveSession, SessionManager


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make():
    clock = Clock()
    return SessionManager(clock=clock), clock


def session(device_id: str, name: str = "Aparelho", log: list | None = None) -> ActiveSession:
    evict = (lambda: log.append(device_id)) if log is not None else (lambda: None)
    return ActiveSession(device_id=device_id, device_name=name, evict=evict)


def test_first_acquire_is_granted():
    manager, _ = make()
    result = manager.acquire(session("a"), takeover=False)
    assert result.status == "granted"
    assert manager.has_active() is True
    assert manager.active().device_id == "a"


def test_second_acquire_is_busy_and_names_the_active_device():
    manager, _ = make()
    manager.acquire(session("a", "Moto G"), takeover=False)
    result = manager.acquire(session("b", "Pixel"), takeover=False)
    assert result.status == "busy"
    assert result.active_device_name == "Moto G"
    assert manager.active().device_id == "a"


def test_takeover_evicts_previous_and_grants():
    manager, _ = make()
    evicted: list[str] = []
    manager.acquire(session("a", log=evicted), takeover=False)
    result = manager.acquire(session("b", log=evicted), takeover=True)
    assert result.status == "granted"
    assert evicted == ["a"]
    assert manager.active().device_id == "b"


def test_same_device_reacquire_does_not_evict_itself():
    manager, _ = make()
    evicted: list[str] = []
    manager.acquire(session("a", log=evicted), takeover=False)
    result = manager.acquire(session("a", log=evicted), takeover=False)
    assert result.status == "granted"
    assert evicted == []


def test_release_frees_session():
    manager, _ = make()
    manager.acquire(session("a"), takeover=False)
    manager.release("a")
    assert manager.has_active() is False
    assert manager.active() is None


def test_release_of_non_active_device_is_noop():
    manager, _ = make()
    manager.acquire(session("a"), takeover=False)
    manager.release("b")
    assert manager.active().device_id == "a"


def test_stale_session_expires_after_15s_without_touch():
    manager, clock = make()
    manager.acquire(session("a"), takeover=False)
    clock.now += 16
    assert manager.active() is None
    assert manager.acquire(session("b"), takeover=False).status == "granted"


def test_touch_keeps_session_alive():
    manager, clock = make()
    manager.acquire(session("a"), takeover=False)
    for _ in range(4):
        clock.now += 10
        manager.touch("a")
    assert manager.active().device_id == "a"


def test_touch_of_other_device_does_not_keep_session_alive():
    manager, clock = make()
    manager.acquire(session("a"), takeover=False)
    clock.now += 10
    manager.touch("b")
    clock.now += 10
    assert manager.active() is None


def test_release_with_old_session_object_keeps_the_new_one():
    manager, _ = make()
    old = session("a")
    manager.acquire(old, takeover=False)
    new = session("a")
    manager.acquire(new, takeover=False)
    manager.release("a", session=old)
    assert manager.active() is new
    manager.release("a", session=new)
    assert manager.active() is None
