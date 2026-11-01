"""Logica de recuperacao do provider do Windows, com dubles no lugar do codigo nativo."""

from typing import ClassVar

import pytest

from pcx_agent.sensors.windows import provider as provider_module
from pcx_agent.sensors.windows.gpu import AdapterInfo

LUID = "0x00000000_0x0000d1a5"
GIB = 1024**3
ENGINE = "pid_1_luid_0x00000000_0x0000D1A5_phys_0_eng_0_engtype_3D"
MEMORY = f"luid_{LUID}_phys_0"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakePdh:
    instances: ClassVar[list] = []

    def __init__(self) -> None:
        FakePdh.instances.append(self)
        self.fail = False
        self.closed = False

    def read(self):
        if self.fail:
            raise OSError("PDH quebrou")
        return (
            [{"InstanceName": ENGINE, "CookedValue": 42.0}],
            [{"InstanceName": MEMORY, "CookedValue": 2.0 * GIB}],
        )

    def close(self) -> None:
        self.closed = True


class FakeNvml:
    instances: ClassVar[list] = []
    broken: ClassVar[bool] = False

    def __init__(self) -> None:
        if FakeNvml.broken:
            raise OSError("NVML indisponivel")
        FakeNvml.instances.append(self)
        self.fail = False
        self.closed = False

    def read(self):
        if self.fail:
            raise OSError("GPU_IS_LOST")
        return {"NVIDIA Teste": 61.0}

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def make(monkeypatch):
    FakePdh.instances = []
    FakeNvml.instances = []
    FakeNvml.broken = False
    monkeypatch.setattr(provider_module.native, "PdhGpuCounters", FakePdh)
    monkeypatch.setattr(provider_module.native, "NvmlTemperatures", FakeNvml)
    monkeypatch.setattr(
        provider_module.native,
        "list_adapters",
        lambda: {LUID: AdapterInfo("NVIDIA Teste", 8 * GIB)},
    )
    clock = Clock()
    instances = []

    def build():
        instance = provider_module.WindowsSensorProvider(clock=clock)
        instances.append(instance)
        return instance, clock

    yield build
    for instance in instances:
        instance.close()


def test_normal_read_has_usage_vram_and_temperature(make):
    provider, _ = make()
    gpu = provider.read().gpus[0]
    assert (gpu.usage_percent, gpu.temp_c) == (42.0, 61.0)
    assert (gpu.vram_used_bytes, gpu.vram_total_bytes) == (2 * GIB, 8 * GIB)


def test_nvml_failure_keeps_gpu_usage_with_none_temperature(make):
    provider, _ = make()
    FakeNvml.instances[0].fail = True
    gpu = provider.read().gpus[0]
    assert gpu.usage_percent == 42.0
    assert gpu.temp_c is None
    assert gpu.vram_used_bytes == 2 * GIB
    assert "gpu.temp" not in provider.capabilities()


def test_nvml_recovers_after_retry_window(make):
    provider, clock = make()
    FakeNvml.instances[0].fail = True
    assert provider.read().gpus[0].temp_c is None
    assert FakeNvml.instances[0].closed is True
    clock.now += 30
    assert provider.read().gpus[0].temp_c is None  # ainda dentro da espera
    assert len(FakeNvml.instances) == 1
    clock.now += 31
    gpu = provider.read().gpus[0]
    assert len(FakeNvml.instances) == 2
    assert gpu.temp_c == 61.0
    assert "gpu.temp" in provider.capabilities()


def test_pdh_failure_returns_no_gpus_then_reopens(make):
    provider, clock = make()
    FakePdh.instances[0].fail = True
    assert provider.read().gpus == []
    assert FakePdh.instances[0].closed is True
    clock.now += 61
    assert provider.read().gpus[0].usage_percent == 42.0
    assert len(FakePdh.instances) == 2


def test_machine_without_nvml_has_no_temperature_and_no_error(make):
    FakeNvml.broken = True
    provider, _ = make()
    gpu = provider.read().gpus[0]
    assert gpu.temp_c is None and gpu.usage_percent == 42.0
