"""Acesso nativo ao Windows: contadores PDH, DXGI (ctypes) e NVML. Importar so no Windows."""

import ctypes as ct
import logging
import uuid
from ctypes import wintypes

from pcx_agent.sensors.windows.gpu import AdapterInfo

logger = logging.getLogger("pcx_agent.sensors.windows")


class PdhGpuCounters:
    """Consulta PDH aberta uma vez e lida a cada volta (sem sleep dentro da leitura)."""

    def __init__(self) -> None:
        import win32pdh

        self._pdh = win32pdh
        self._query = win32pdh.OpenQuery()
        try:
            self._engine = win32pdh.AddEnglishCounter(
                self._query, r"\GPU Engine(*)\Utilization Percentage"
            )
            self._memory = win32pdh.AddEnglishCounter(
                self._query, r"\GPU Adapter Memory(*)\Dedicated Usage"
            )
            win32pdh.CollectQueryData(self._query)  # leitura base: taxas precisam de 2 pontos
        except Exception:
            win32pdh.CloseQuery(self._query)
            raise

    def _array(self, counter) -> list[dict]:
        try:
            values = self._pdh.GetFormattedCounterArray(counter, self._pdh.PDH_FMT_DOUBLE)
        except self._pdh.error:
            return []  # ainda sem dados (primeira leitura) ou sem instancias
        return [{"InstanceName": name, "CookedValue": value} for name, value in values.items()]

    def read(self) -> tuple[list[dict], list[dict]]:
        """Devolve (amostras de motores, amostras de memoria)."""
        self._pdh.CollectQueryData(self._query)
        return self._array(self._engine), self._array(self._memory)

    def close(self) -> None:
        self._pdh.CloseQuery(self._query)


class _Luid(ct.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _AdapterDesc1(ct.Structure):
    _fields_ = [
        ("Description", wintypes.WCHAR * 128),
        ("VendorId", wintypes.UINT),
        ("DeviceId", wintypes.UINT),
        ("SubSysId", wintypes.UINT),
        ("Revision", wintypes.UINT),
        ("DedicatedVideoMemory", ct.c_size_t),
        ("DedicatedSystemMemory", ct.c_size_t),
        ("SharedSystemMemory", ct.c_size_t),
        ("AdapterLuid", _Luid),
        ("Flags", wintypes.UINT),
    ]


_DXGI_ERROR_NOT_FOUND = 0x887A0002
_DXGI_ADAPTER_FLAG_SOFTWARE = 2


def _method(pointer, index, restype, *argtypes):
    table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
    return ct.WINFUNCTYPE(restype, ct.c_void_p, *argtypes)(table[index])


def _check(result: int, operation: str) -> None:
    if result < 0:
        raise OSError(f"{operation} falhou: 0x{result & 0xFFFFFFFF:08x}")


def list_adapters() -> dict[str, AdapterInfo]:
    """{LUID minusculo: AdapterInfo} dos adaptadores DXGI que nao sao de software."""
    dxgi = ct.WinDLL("dxgi.dll")
    dxgi.CreateDXGIFactory1.argtypes = [ct.c_void_p, ct.POINTER(ct.c_void_p)]
    dxgi.CreateDXGIFactory1.restype = wintypes.LONG
    iid = (ct.c_ubyte * 16).from_buffer_copy(
        uuid.UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le  # IID_IDXGIFactory1
    )
    factory = ct.c_void_p()
    _check(dxgi.CreateDXGIFactory1(ct.byref(iid), ct.byref(factory)), "CreateDXGIFactory1")
    if not factory.value:
        raise OSError("DXGI nao devolveu uma fabrica valida.")
    try:
        enum_adapters = _method(
            factory, 12, wintypes.LONG, wintypes.UINT, ct.POINTER(ct.c_void_p)
        )  # IDXGIFactory1::EnumAdapters1
        found: dict[str, AdapterInfo] = {}
        index = 0
        while True:
            adapter = ct.c_void_p()
            result = enum_adapters(factory, index, ct.byref(adapter))
            if result & 0xFFFFFFFF == _DXGI_ERROR_NOT_FOUND:
                break
            _check(result, "EnumAdapters1")
            if not adapter.value:
                raise OSError("DXGI nao devolveu um adaptador valido.")
            try:
                desc = _AdapterDesc1()
                get_desc = _method(
                    adapter, 10, wintypes.LONG, ct.POINTER(_AdapterDesc1)
                )  # IDXGIAdapter1::GetDesc1
                _check(get_desc(adapter, ct.byref(desc)), "GetDesc1")
                name = desc.Description.strip()
                if not desc.Flags & _DXGI_ADAPTER_FLAG_SOFTWARE and name:
                    luid = (
                        f"0x{desc.AdapterLuid.HighPart & 0xFFFFFFFF:08x}_"
                        f"0x{desc.AdapterLuid.LowPart:08x}"
                    )
                    found[luid] = AdapterInfo(name, int(desc.DedicatedVideoMemory), int(desc.VendorId))
            finally:
                _method(adapter, 2, wintypes.ULONG)(adapter)  # Release
            index += 1
        return found
    finally:
        _method(factory, 2, wintypes.ULONG)(factory)  # Release


class NvmlTemperatures:
    """Temperatura das GPUs NVIDIA, indexada pelo nome do adaptador."""

    def __init__(self) -> None:
        import pynvml

        self._nvml = pynvml
        pynvml.nvmlInit()
        try:
            count = pynvml.nvmlDeviceGetCount()
            if count == 0:
                raise OSError("NVML nao encontrou GPUs.")
            self._handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(count)]
        except Exception:
            pynvml.nvmlShutdown()
            raise

    def read(self) -> dict[str, float]:
        temps: dict[str, float] = {}
        for handle in self._handles:
            name = self._nvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", "replace")
            temps[name] = float(
                self._nvml.nvmlDeviceGetTemperature(handle, self._nvml.NVML_TEMPERATURE_GPU)
            )
        return temps

    def close(self) -> None:
        self._nvml.nvmlShutdown()
