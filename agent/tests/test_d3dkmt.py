"""Temperatura da GPU pelo driver de video do Windows (o mesmo caminho do Gerenciador de Tarefas)."""

import struct
import sys

import pytest

from pcx_agent.sensors.windows.d3dkmt import (
    KMTQAITYPE_ADAPTERPERFDATA_CAPS,
    PERFDATA_SIZE,
    PERFDATACAPS_SIZE,
    luid_parts,
    parse_perfdata,
    parse_perfdata_caps,
)

windows = pytest.mark.skipif(sys.platform != "win32", reason="so no Windows")


def perfdata(temperature_deci_c: int, fan_rpm: int = 1200, power: int = 250) -> bytes:
    """D3DKMT_ADAPTER_PERFDATA: UINT32 + 4 de alinhamento, 5 ULONGLONG, 3 ULONG, 1 UCHAR + 3."""
    return struct.pack(
        "<I4x5Q3IB3x", 0, 2_250_000_000, 2_250_000_000, 2_500_000_000, 0, 0, fan_rpm, power, temperature_deci_c, 1
    )


def test_layout_has_64_bytes_and_temperature_at_offset_56():
    raw = perfdata(520)
    assert len(raw) == PERFDATA_SIZE == 64
    assert struct.unpack_from("<I", raw, 56)[0] == 520


def test_reads_temperature_in_tenths_of_degree():
    assert parse_perfdata(perfdata(520)) == 52.0
    assert parse_perfdata(perfdata(463)) == 46.3


@pytest.mark.parametrize("value", [0, 1501, 0xFFFFFFFF])
def test_zero_or_absurd_temperature_means_no_reading(value):
    """Driver sem sensor devolve 0; valores acima de 150 C sao lixo."""
    assert parse_perfdata(perfdata(value)) is None


def test_short_buffer_means_no_reading():
    assert parse_perfdata(perfdata(520)[:57]) is None
    assert parse_perfdata(b"") is None


def perfdata_caps(warning_deci_c: int, maximum_deci_c: int = 950) -> bytes:
    """D3DKMT_ADAPTER_PERFDATACAPS: UINT32 + 4 de alinhamento, 2 ULONGLONG, 3 ULONG + 4 de alinhamento."""
    return struct.pack("<I4x2Q3I4x", 0, 1, 2, 2000, maximum_deci_c, warning_deci_c)


def test_caps_layout_has_40_bytes_and_warning_at_offset_32():
    raw = perfdata_caps(830)
    assert len(raw) == PERFDATACAPS_SIZE == 40
    assert KMTQAITYPE_ADAPTERPERFDATA_CAPS == 63
    assert struct.unpack_from("<I", raw, 32)[0] == 830


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (perfdata_caps(830), 83.0),
        (perfdata_caps(0), None),
        (perfdata_caps(1600), None),
        (perfdata_caps(830)[:35], None),
    ],
    ids=["830", "zero", "1600", "curto"],
)
def test_parse_perfdata_caps(raw, expected):
    assert parse_perfdata_caps(raw) == expected


@pytest.mark.parametrize(
    ("luid", "parts"),
    [
        ("0x00000000_0x00009962", (0x9962, 0)),
        ("0x00000001_0x0000d1a5", (0xD1A5, 1)),
        ("0xffffffff_0x00000010", (0x10, -1)),  # HighPart e um LONG com sinal
    ],
)
def test_luid_parts_back_to_low_and_high(luid, parts):
    assert luid_parts(luid) == parts


@pytest.mark.parametrize("bad", ["", "0x1", "luid_0x0_0x1", "0xzz_0x01"])
def test_luid_parts_rejects_garbage(bad):
    with pytest.raises(ValueError):
        luid_parts(bad)


@windows
def test_real_adapters_are_read_without_errors():
    """No runner do GitHub nao ha placa de verdade: so nao pode quebrar."""
    from pcx_agent.sensors.windows import native
    from pcx_agent.sensors.windows.d3dkmt import D3dkmtTemperatures

    temps = D3dkmtTemperatures()
    try:
        result = temps.read(list(native.list_adapters()))
    finally:
        temps.close()
    assert isinstance(result, dict)
    assert all(isinstance(v, float) and 0 < v <= 150 for v in result.values())


@windows
def test_read_warnings_real_adapters_no_exception():
    from pcx_agent.sensors.windows import native
    from pcx_agent.sensors.windows.d3dkmt import D3dkmtTemperatures

    temps = D3dkmtTemperatures()
    try:
        result = temps.read_warnings(list(native.list_adapters()))
    finally:
        temps.close()
    assert isinstance(result, dict)
    assert all(isinstance(v, float) and 0 < v <= 150 for v in result.values())


def test_ctypes_structures_have_the_windows_sizes():
    """Tamanhos do d3dkmthk.h em 64 bits: um campo errado aqui so quebraria no Windows."""
    import ctypes

    from pcx_agent.sensors.windows import d3dkmt

    assert ctypes.sizeof(d3dkmt._OpenAdapterFromLuid) == 12  # LUID (8) + D3DKMT_HANDLE (4)
    assert ctypes.sizeof(d3dkmt._CloseAdapter) == 4
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        # hAdapter (4) + Type (4) + ponteiro (8) + tamanho (4) + alinhamento (4)
        assert ctypes.sizeof(d3dkmt._QueryAdapterInfo) == 24
        assert d3dkmt._QueryAdapterInfo.pPrivateDriverData.offset == 8
