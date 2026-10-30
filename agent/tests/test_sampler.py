import asyncio

import pytest

from pcx_agent.sampler import Sampler
from pcx_agent.storage.db import Database
from pcx_agent.storage.history import HistoryStore
from tests.test_fake_sensors import make_snapshot


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class ScriptedProvider:
    """Devolve as leituras em ordem; um item Exception e levantado."""

    def __init__(self, items) -> None:
        self.items = list(items)
        self.calls = 0

    def capabilities(self) -> set[str]:
        return {"cpu"}

    def read(self):
        item = self.items[min(self.calls, len(self.items) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return make_snapshot(cpu_total=item)

    def close(self) -> None:
        return None


@pytest.fixture
def parts(tmp_path):
    db = Database(tmp_path / "pcx.db")
    history = HistoryStore(db)
    clock = Clock()
    wall = Clock()
    wall.now = 5000.0
    yield history, clock, wall
    db.close()


def build(parts, items, active=lambda: False, on_snapshot=None, **kwargs):
    history, clock, wall = parts
    provider = ScriptedProvider(items)
    sampler = Sampler(
        provider, history, active, on_snapshot=on_snapshot, clock=clock, wall=wall, **kwargs
    )
    return sampler, provider


async def test_tick_updates_latest(parts):
    sampler, _ = build(parts, [42.0])
    assert sampler.latest is None
    await sampler.tick()
    assert sampler.latest.cpu_total == 42.0


def test_interval_is_5s_idle_and_1s_active(parts):
    state = {"active": False}
    sampler, _ = build(parts, [1.0], active=lambda: state["active"])
    assert sampler.current_interval() == 5.0
    state["active"] = True
    assert sampler.current_interval() == 1.0


async def test_on_snapshot_called_only_with_active_session(parts):
    state = {"active": False}
    received = []
    sampler, _ = build(parts, [1.0], active=lambda: state["active"], on_snapshot=received.append)
    await sampler.tick()
    assert received == []
    state["active"] = True
    await sampler.tick()
    assert len(received) == 1


async def test_flush_writes_avg_and_max_after_5s(parts):
    history, clock, wall = parts
    sampler, _ = build(parts, [10.0, 20.0, 60.0])
    await sampler.tick()
    clock.now = 2.0
    await sampler.tick()
    clock.now = 5.0
    await sampler.tick()
    points = history.query("cpu.total", "15m", wall.now)
    assert len(points) == 1
    assert points[0].avg == 30.0
    assert points[0].max == 60.0


async def test_no_flush_before_5s(parts):
    history, clock, wall = parts
    sampler, _ = build(parts, [10.0, 20.0])
    await sampler.tick()
    clock.now = 4.9
    await sampler.tick()
    assert history.query("cpu.total", "15m", wall.now) == []


async def test_accumulators_restart_after_flush(parts):
    history, clock, wall = parts
    sampler, _ = build(parts, [100.0, 100.0, 10.0, 20.0])
    await sampler.tick()
    clock.now = 5.0
    await sampler.tick()
    wall.now += 5
    await sampler.tick()
    clock.now = 10.0
    await sampler.tick()
    points = history.query("cpu.total", "15m", wall.now)
    assert [p.avg for p in points] == [100.0, 15.0]


async def test_provider_error_keeps_last_snapshot_and_loop_continues(parts, caplog):
    sampler, _ = build(parts, [10.0, OSError("driver reiniciou"), 30.0])
    await sampler.tick()
    await sampler.tick()
    assert sampler.latest.cpu_total == 10.0
    assert "driver reiniciou" in caplog.text
    await sampler.tick()
    assert sampler.latest.cpu_total == 30.0


async def test_prune_runs_hourly(parts):
    history, clock, wall = parts
    history.record(wall.now - 90000, "cpu.total", 1, 1)
    sampler, _ = build(parts, [10.0])
    await sampler.tick()
    clock.now = 3601.0
    wall.now += 3601
    await sampler.tick()
    old = history._db.query("SELECT COUNT(*) AS n FROM history WHERE ts < ?", (wall.now - 86400,))
    assert old[0]["n"] == 0


async def test_run_stops_on_stop(parts):
    sampler, _ = build(parts, [10.0], idle_interval=0.01)
    task = asyncio.create_task(sampler.run())
    for _ in range(100):
        if sampler.latest is not None:
            break
        await asyncio.sleep(0.01)
    assert sampler.latest is not None
    sampler.stop()
    await asyncio.wait_for(task, timeout=1.0)
