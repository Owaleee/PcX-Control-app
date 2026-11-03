"""Temperatura da GPU pelo driver de video do Windows (D3DKMT).

E o mesmo caminho do Gerenciador de Tarefas e vale para NVIDIA, AMD e Intel, com drivers WDDM
2.4 ou mais novos. A interpretacao dos bytes (`parse_perfdata`, `luid_parts`) e pura e testavel
em qualquer sistema; so `D3dkmtTemperatures` precisa do Windows.
"""

import ctypes as ct
import re
import struct

# D3DKMT_ADAPTER_PERFDATA (d3dkmthk.h): UINT32 PhysicalAdapterIndex, 4 bytes de alinhamento,
# 5 ULONGLONG (frequencias e banda), ULONG FanRPM, ULONG Power, ULONG Temperature (decimos de
# grau Celsius), UCHAR PowerStateOverride e alinhamento ate 64 bytes.
PERFDATA_SIZE = 64
_TEMPERATURE_OFFSET = 56
_MAX_DECI_C = 1500  # acima de 150 C e lixo do driver
KMTQAITYPE_ADAPTERPERFDATA = 62
_LUID = re.compile(r"^0x([0-9a-f]{1,8})_0x([0-9a-f]{1,8})$", re.IGNORECASE)


def parse_perfdata(raw: bytes) -> float | None:
    """Temperatura em graus Celsius, ou None se o driver nao tiver o sensor."""
    if len(raw) < _TEMPERATURE_OFFSET + 4:
        return None
    (deci_c,) = struct.unpack_from("<I", raw, _TEMPERATURE_OFFSET)
    if deci_c == 0 or deci_c > _MAX_DECI_C:
        return None
    return round(deci_c / 10.0, 1)


def luid_parts(luid: str) -> tuple[int, int]:
    """'0xHHHHHHHH_0xLLLLLLLL' (formato do agente) -> (LowPart, HighPart com sinal)."""
    match = _LUID.match(luid)
    if match is None:
        raise ValueError(f"LUID invalido: {luid!r}")
    high, low = int(match.group(1), 16), int(match.group(2), 16)
    if high >= 0x80000000:
        high -= 0x100000000
    return low, high


class _Luid(ct.Structure):
    _fields_ = [("LowPart", ct.c_uint32), ("HighPart", ct.c_int32)]


class _OpenAdapterFromLuid(ct.Structure):
    _fields_ = [("AdapterLuid", _Luid), ("hAdapter", ct.c_uint32)]


class _QueryAdapterInfo(ct.Structure):
    _fields_ = [
        ("hAdapter", ct.c_uint32),
        ("Type", ct.c_int32),
        ("pPrivateDriverData", ct.c_void_p),
        ("PrivateDriverDataSize", ct.c_uint32),
    ]


class _CloseAdapter(ct.Structure):
    _fields_ = [("hAdapter", ct.c_uint32)]


class D3dkmtTemperatures:
    """Temperatura por LUID da placa. Placas sem o sensor simplesmente nao aparecem."""

    def __init__(self) -> None:
        gdi = ct.WinDLL("gdi32.dll")
        self._open = gdi.D3DKMTOpenAdapterFromLuid
        self._query = gdi.D3DKMTQueryAdapterInfo
        self._close = gdi.D3DKMTCloseAdapter
        for function in (self._open, self._query, self._close):
            function.restype = ct.c_long  # NTSTATUS: 0 e sucesso
        self._open.argtypes = [ct.POINTER(_OpenAdapterFromLuid)]
        self._query.argtypes = [ct.POINTER(_QueryAdapterInfo)]
        self._close.argtypes = [ct.POINTER(_CloseAdapter)]

    def _read_one(self, luid: str) -> float | None:
        low, high = luid_parts(luid)
        opened = _OpenAdapterFromLuid(_Luid(low, high), 0)
        if self._open(ct.byref(opened)) != 0:
            return None
        try:
            buffer = (ct.c_ubyte * PERFDATA_SIZE)()  # PhysicalAdapterIndex = 0 (zerado)
            info = _QueryAdapterInfo(
                opened.hAdapter, KMTQAITYPE_ADAPTERPERFDATA, ct.cast(buffer, ct.c_void_p), PERFDATA_SIZE
            )
            if self._query(ct.byref(info)) != 0:
                return None  # driver antigo (sem WDDM 2.4) ou sem o dado
            return parse_perfdata(bytes(buffer))
        finally:
            self._close(ct.byref(_CloseAdapter(opened.hAdapter)))

    def read(self, luids: list[str]) -> dict[str, float]:
        result: dict[str, float] = {}
        for luid in luids:
            value = self._read_one(luid)
            if value is not None:
                result[luid] = value
        return result

    def close(self) -> None:
        """Nada fica aberto entre leituras."""
