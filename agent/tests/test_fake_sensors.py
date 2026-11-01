from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pcx_agent.sensors.base import DiskVolume, GpuReading, Snapshot
from pcx_agent.sensors.fake import FakeSensorProvider

METRIC_KEYS = {
    "cpu.total",
    "ram.percent",
    "net.down_bps",
    "net.up_bps",
    "disk.read_bps",
    "disk.write_bps",
    "gpu.usage",
    "gpu.temp",
    "gpu.vram_percent",
}


def make_snapshot(**overrides) -> Snapshot:
    data = {
        "t": datetime.now(UTC),
        "cpu_total": 10.0,
        "ram_percent": 50.0,
        "ram_used_bytes": 8 * 1024**3,
        "ram_total_bytes": 16 * 1024**3,
        "disks": [DiskVolume(mount="C:\\", percent=40.0, used_bytes=1, total_bytes=2)],
        "disk_read_bps": 0.0,
        "disk_write_bps": 0.0,
        "net_down_bps": 0.0,
        "net_up_bps": 0.0,
        "gpus": [],
        "host_name": "pc",
        "uptime_s": 10.0,
    
    }
    data.update(overrides)
    return Snapshot(**data)


def test_snapshot_rejects_percent_over_100():
    with pytest.raises(ValidationError):
        make_snapshot(cpu_total=101)


def test_fake_is_deterministic_per_seed():
    a = FakeSensorProvider(seed=7).read()
    b = FakeSensorProvider(seed=7).read()
    assert a.cpu_total == b.cpu_total


def test_fake_declares_capabilities():
    caps = FakeSensorProvider().capabilities()
    assert {"cpu", "ram", "disk", "net", "gpu", "gpu.temp"} <= caps


def test_metrics_keys():
    snap = FakeSensorProvider().read()
    assert METRIC_KEYS <= set(snap.metrics())


def test_metrics_omits_gpu_when_no_gpu():
    metrics = make_snapshot(gpus=[]).metrics()
    assert not any(key.startswith("gpu.") for key in metrics)


def test_metrics_omits_gpu_fields_that_are_none():
    gpu = GpuReading(id="g0", name="GPU", usage_percent=30.0)
    metrics = make_snapshot(gpus=[gpu]).metrics()
    assert metrics["gpu.usage"] == 30.0
    assert "gpu.temp" not in metrics
    assert "gpu.vram_percent" not in metrics
