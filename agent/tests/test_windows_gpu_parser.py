import json
import math
from pathlib import Path

from pcx_agent.sensors.windows.gpu import AdapterInfo, parse_gpu_usage, parse_vram_usage

GIB = 1024**3
RTX = "0x00000000_0x0000d1a5"
OTHER = "0x00000000_0x0000c0de"
ADAPTERS = {
    RTX: AdapterInfo("NVIDIA GeForce RTX 3070", 8 * GIB),
    OTHER: AdapterInfo("Outra GPU", 4 * GIB),
}
DATA = json.loads((Path(__file__).parent / "data" / "pdh_samples.json").read_text())


def sample(name: str, value: float) -> dict:
    return {"InstanceName": name, "CookedValue": value}


def engine(luid: str, phys: int, eng: int, kind: str = "3D", pid: int = 1) -> str:
    return f"pid_{pid}_luid_{luid.upper().replace('0X', '0x')}_phys_{phys}_eng_{eng}_engtype_{kind}"


def by_name(readings):
    return {r.name: r for r in readings}


def test_sums_per_engine_and_takes_busiest():
    readings = by_name(parse_gpu_usage(DATA, ADAPTERS))
    assert readings["NVIDIA GeForce RTX 3070"].usage_percent == 70.0


def test_ignores_software_adapter_luid():
    names = {r.name for r in parse_gpu_usage(DATA, ADAPTERS)}
    assert names == {"NVIDIA GeForce RTX 3070", "Outra GPU"}


def test_ignores_nan_negative_and_malformed_names():
    samples = [
        sample(engine(RTX, 0, 0), math.nan),
        sample(engine(RTX, 0, 1), -5.0),
        sample(engine(RTX, 0, 2), math.inf),
        sample("lixo qualquer", 50.0),
        sample("", 50.0),
        sample(engine(RTX, 0, 3), 20.0),
    ]
    readings = parse_gpu_usage(samples, ADAPTERS)
    assert [r.usage_percent for r in readings] == [20.0]


def test_caps_at_100():
    samples = [sample(engine(RTX, 0, 0, pid=n), 60.0) for n in (1, 2)]
    assert parse_gpu_usage(samples, ADAPTERS)[0].usage_percent == 100.0


def test_empty_samples_returns_empty_list():
    assert parse_gpu_usage([], ADAPTERS) == []
    assert parse_gpu_usage(DATA, {}) == []


def test_two_physical_gpus_listed_separately_and_sorted():
    readings = parse_gpu_usage(DATA, ADAPTERS)
    assert [r.id for r in readings] == sorted(r.id for r in readings)
    assert len(readings) == 2


def test_same_luid_different_phys_are_separate():
    samples = [sample(engine(RTX, 0, 0), 10.0), sample(engine(RTX, 1, 0), 20.0)]
    ids = [r.id for r in parse_gpu_usage(samples, ADAPTERS)]
    assert ids == [f"luid_{RTX}_phys_0", f"luid_{RTX}_phys_1"]


def test_vram_total_comes_from_adapter_info_and_used_from_counters():
    used = {f"luid_{RTX}_phys_0": 3 * GIB}
    readings = by_name(parse_gpu_usage(DATA, ADAPTERS, vram_used=used))
    rtx = readings["NVIDIA GeForce RTX 3070"]
    assert rtx.vram_total_bytes == 8 * GIB
    assert rtx.vram_used_bytes == 3 * GIB
    assert readings["Outra GPU"].vram_used_bytes is None


def test_instance_suffix_with_hash_is_tolerated():
    samples = [sample(engine(RTX, 0, 0) + "#1", 25.0)]
    assert parse_gpu_usage(samples, ADAPTERS)[0].usage_percent == 25.0


def test_parse_vram_usage_reads_adapter_memory_instances():
    samples = [
        sample(f"luid_{RTX}_phys_0", 3 * GIB),
        sample("luid_0x00000000_0x0000BEEF_phys_0", 5.0),
        sample("lixo", 1.0),
        sample(f"luid_{OTHER}_phys_0", math.nan),
    ]
    parsed = parse_vram_usage(samples)
    assert parsed[f"luid_{RTX}_phys_0"] == 3 * GIB
    assert f"luid_{OTHER}_phys_0" not in parsed
    assert "lixo" not in parsed
