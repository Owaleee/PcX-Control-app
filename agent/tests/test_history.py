import pytest

from pcx_agent.storage.db import Database
from pcx_agent.storage.history import VALID_RANGES, HistoryStore

NOW = 1_000_000.0


@pytest.fixture
def store(tmp_path):
    db = Database(tmp_path / "pcx.db")
    yield HistoryStore(db)
    db.close()


def test_query_returns_only_requested_range(store):
    store.record(NOW - 20 * 60, "cpu.total", 10, 20)
    store.record(NOW - 5 * 60, "cpu.total", 30, 40)
    assert [p.avg for p in store.query("cpu.total", "15m", NOW)] == [30]
    assert [p.avg for p in store.query("cpu.total", "1h", NOW)] == [10, 30]


def test_points_are_ordered(store):
    for offset in (300, 100, 200):
        store.record(NOW - offset, "cpu.total", offset, offset)
    times = [p.t for p in store.query("cpu.total", "15m", NOW)]
    assert times == sorted(times)


def test_query_filters_by_metric(store):
    store.record(NOW - 10, "cpu.total", 1, 1)
    store.record(NOW - 10, "ram.percent", 2, 2)
    assert [p.avg for p in store.query("ram.percent", "15m", NOW)] == [2]


def test_point_has_avg_and_max(store):
    store.record(NOW - 10, "cpu.total", 30, 60)
    point = store.query("cpu.total", "15m", NOW)[0]
    assert (point.t, point.avg, point.max) == (NOW - 10, 30, 60)


def test_prune_removes_older_than_24h_and_returns_count(store):
    store.record(NOW - 25 * 3600, "cpu.total", 1, 1)
    store.record(NOW - 30 * 3600, "cpu.total", 1, 1)
    store.record(NOW - 3600, "cpu.total", 2, 2)
    assert store.prune(NOW) == 2
    assert [p.avg for p in store.query("cpu.total", "24h", NOW)] == [2]


def test_query_unknown_metric_returns_empty(store):
    store.record(NOW - 10, "cpu.total", 1, 1)
    assert store.query("nao.existe", "15m", NOW) == []


def test_query_invalid_range_raises_value_error(store):
    with pytest.raises(ValueError):
        store.query("cpu.total", "2h", NOW)


def test_record_same_ts_metric_overwrites(store):
    store.record(NOW - 10, "cpu.total", 1, 1)
    store.record(NOW - 10, "cpu.total", 5, 9)
    points = store.query("cpu.total", "15m", NOW)
    assert len(points) == 1 and points[0].avg == 5


def test_valid_ranges_constant():
    assert set(VALID_RANGES) == {"15m", "1h", "24h"}
