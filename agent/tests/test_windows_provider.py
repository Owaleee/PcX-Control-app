import sys

import pytest

from pcx_agent.sensors.base import Snapshot

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(sys.platform != "win32", reason="exige Windows"),
]


@pytest.fixture
def provider():
    from pcx_agent.sensors.windows.provider import WindowsSensorProvider

    instance = WindowsSensorProvider()
    yield instance
    instance.close()


def test_read_returns_valid_snapshot_even_without_gpu(provider):
    snapshot = provider.read()
    assert isinstance(snapshot, Snapshot)
    Snapshot.model_validate(snapshot.model_dump())
    assert snapshot.ram_total_bytes > 0
    assert snapshot.host_name


def test_two_reads_do_not_raise_and_second_has_net_rates(provider):
    provider.read()
    second = provider.read()
    assert second.net_down_bps >= 0 and second.net_up_bps >= 0
    assert second.disk_read_bps >= 0 and second.disk_write_bps >= 0


def test_capabilities_include_gpu_temp_only_when_nvml_loads(provider):
    capabilities = provider.capabilities()
    assert {"cpu", "ram", "disk", "net"} <= capabilities
    assert ("gpu.temp" in capabilities) == (provider._nvml is not None)
    assert ("gpu" in capabilities) == (provider._pdh is not None)


def test_dxgi_adapters_listing_does_not_raise():
    from pcx_agent.sensors.windows import native

    adapters = native.list_adapters()
    assert isinstance(adapters, dict)
