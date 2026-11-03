"""Fabricante, ordem das placas, descricao para o log e log com limite de frequencia."""

import logging

import pytest

from pcx_agent.logs import redact
from pcx_agent.ratelimit_log import RateLimitedLog
from pcx_agent.sensors.windows.gpu import (
    AdapterInfo,
    describe_adapters,
    parse_gpu_usage,
    vendor_name,
)

GIB = 1024**3
MIB = 1024**2
DEDICATED = "0x00000000_0x00009962"
INTEGRATED = "0x00000000_0x0000a1b2"


def engine(luid: str, value: float, eng: int = 0) -> dict:
    return {"InstanceName": f"pid_1_luid_{luid}_phys_0_eng_{eng}_engtype_3D", "CookedValue": value}


@pytest.mark.parametrize(
    ("vendor_id", "expected"),
    [(0x10DE, "nvidia"), (0x1002, "amd"), (0x8086, "intel"), (0x1414, "outra"), (0, "outra")],
)
def test_vendor_name(vendor_id, expected):
    assert vendor_name(vendor_id) == expected


def test_readings_carry_vendor():
    adapters = {DEDICATED: AdapterInfo("AMD Radeon RX 7600", 8 * GIB, 0x1002)}
    (reading,) = parse_gpu_usage([engine(DEDICATED, 10.0)], adapters)
    assert reading.vendor == "amd"


def test_adapter_without_vendor_id_is_outra():
    (reading,) = parse_gpu_usage([engine(DEDICATED, 10.0)], {DEDICATED: AdapterInfo("Placa", GIB)})
    assert reading.vendor == "outra"


def test_dedicated_card_comes_first_even_with_lower_luid_order():
    # A integrada tem o LUID "maior" na ordem alfabetica, mas a dedicada tem mais VRAM.
    adapters = {
        INTEGRATED: AdapterInfo("Intel UHD Graphics 770", 512 * MIB, 0x8086),
        DEDICATED: AdapterInfo("AMD Radeon RX 7600", 8 * GIB, 0x1002),
    }
    samples = [engine(INTEGRATED, 50.0), engine(DEDICATED, 5.0)]
    names = [r.name for r in parse_gpu_usage(samples, adapters)]
    assert names == ["AMD Radeon RX 7600", "Intel UHD Graphics 770"]
    # A ordem nao depende da ordem das amostras.
    assert [r.name for r in parse_gpu_usage(samples[::-1], adapters)] == names


def test_same_vram_keeps_a_stable_order():
    adapters = {
        DEDICATED: AdapterInfo("Placa A", 8 * GIB, 0x10DE),
        INTEGRATED: AdapterInfo("Placa B", 8 * GIB, 0x10DE),
    }
    samples = [engine(INTEGRATED, 1.0), engine(DEDICATED, 1.0)]
    assert [r.id for r in parse_gpu_usage(samples, adapters)] == [
        f"luid_{DEDICATED}_phys_0",
        f"luid_{INTEGRATED}_phys_0",
    ]


def test_describe_adapters_one_line_per_card_dedicated_first():
    adapters = {
        INTEGRATED: AdapterInfo("Intel UHD Graphics 770", 512 * MIB, 0x8086),
        DEDICATED: AdapterInfo("AMD Radeon RX 7600", 8 * GIB, 0x1002),
    }
    assert describe_adapters(adapters) == [
        "AMD Radeon RX 7600 | fabricante amd (VendorId 0x1002) | VRAM 8.0 GiB | LUID 0x00000000_0x00009962",
        "Intel UHD Graphics 770 | fabricante intel (VendorId 0x8086) | VRAM 0.5 GiB | LUID 0x00000000_0x0000a1b2",
    ]


def test_describe_adapters_survives_the_secret_filter():
    """O filtro do log esconde sequencias longas; o LUID tem que continuar legivel."""
    adapters = {DEDICATED: AdapterInfo("AMD Radeon RX 7600", 8 * GIB, 0x1002)}
    (line,) = describe_adapters(adapters)
    assert redact(line) == line


def test_describe_adapters_empty():
    assert describe_adapters({}) == []


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_rate_limited_log_once_per_minute_per_key(caplog):
    clock = Clock()
    log = RateLimitedLog(logging.getLogger("pcx_agent.teste"), interval_s=60, clock=clock)
    with caplog.at_level(logging.DEBUG, logger="pcx_agent.teste"):
        log.report("pdh", "PDH falhou: %s", "erro 1")
        clock.now += 30
        log.report("pdh", "PDH falhou: %s", "erro 2")
        log.report("nvml", "NVML falhou")
        clock.now += 31
        log.report("pdh", "PDH falhou: %s", "erro 3")
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["PDH falhou: erro 1", "NVML falhou", "PDH falhou: erro 3"]
    # As repeticoes caladas vao para o nivel DEBUG, sem sumir de vez.
    debug = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert debug == ["PDH falhou: erro 2"]


def test_rate_limited_log_passes_exception_info(caplog):
    log = RateLimitedLog(logging.getLogger("pcx_agent.teste"), interval_s=60, clock=Clock())
    with caplog.at_level(logging.WARNING, logger="pcx_agent.teste"):
        try:
            raise OSError("driver")
        except OSError:
            log.report("dxgi", "DXGI falhou", exc_info=True)
    assert caplog.records[0].exc_info is not None
