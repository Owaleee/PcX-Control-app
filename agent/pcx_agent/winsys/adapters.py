"""Placas de rede lidas do Windows (GetAdaptersAddresses): nome, driver, tipo, IPv4 e gateway.

O nome da conexao a pessoa pode renomear; a descricao do driver e o tipo (IfType) nao.
A conversao dos registros para NetInterface (interfaces_from_records) e pura e roda em qualquer
sistema; so a leitura (read_adapters) usa o ctypes e exige o Windows.
"""

import ctypes
import socket
from ctypes import wintypes

from pcx_agent.network import NetInterface

AF_INET = 2
GAA_FLAG_SKIP_ANYCAST = 0x2
GAA_FLAG_SKIP_MULTICAST = 0x4
GAA_FLAG_SKIP_DNS_SERVER = 0x8
GAA_FLAG_INCLUDE_GATEWAYS = 0x80
FLAGS = (
    GAA_FLAG_INCLUDE_GATEWAYS | GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_DNS_SERVER
)
ERROR_SUCCESS = 0
ERROR_BUFFER_OVERFLOW = 111
START_BUFFER_BYTES = 15 * 1024
MAX_TRIES = 3
IF_TYPE_ETHERNET = 6
IF_TYPE_WIFI = 71
OPER_STATUS_UP = 1


def classify_if_type(if_type: int) -> str:
    if if_type == IF_TYPE_ETHERNET:
        return "ethernet"
    if if_type == IF_TYPE_WIFI:
        return "wifi"
    return "outra"


def interfaces_from_records(records: list[dict]) -> list[NetInterface]:
    """Registros crus (um por placa) -> NetInterface; placa sem IPv4 fica de fora."""
    found = []
    for record in records:
        if not record.get("ipv4"):
            continue
        found.append(
            NetInterface(
                name=record.get("name") or "",
                ipv4=record["ipv4"],
                up=record.get("oper_status") == OPER_STATUS_UP,
                description=record.get("description") or "",
                kind=classify_if_type(int(record.get("if_type", 0))),
                has_gateway=bool(record.get("has_gateway")),
            )
        )
    return found


class SocketAddress(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", ctypes.c_int)]


class UnicastAddress(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("Flags", wintypes.DWORD),
        ("Next", ctypes.c_void_p),
        ("Address", SocketAddress),
    ]


class SockaddrIn(ctypes.Structure):
    _fields_ = [("family", ctypes.c_ushort), ("port", ctypes.c_ushort), ("addr", ctypes.c_ubyte * 4)]


class AdapterAddresses(ctypes.Structure):
    """IP_ADAPTER_ADDRESSES ate FirstGatewayAddress, na ordem documentada."""

    _fields_ = [
        ("Length", wintypes.ULONG),
        ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.c_void_p),
        ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.c_void_p),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_wchar_p),
        ("Description", ctypes.c_wchar_p),
        ("FriendlyName", ctypes.c_wchar_p),
        ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", wintypes.ULONG),
        ("Flags", wintypes.ULONG),
        ("Mtu", wintypes.ULONG),
        ("IfType", wintypes.ULONG),
        ("OperStatus", ctypes.c_int),
        ("Ipv6IfIndex", wintypes.DWORD),
        ("ZoneIndices", wintypes.ULONG * 16),
        ("FirstPrefix", ctypes.c_void_p),
        ("TransmitLinkSpeed", ctypes.c_ulonglong),
        ("ReceiveLinkSpeed", ctypes.c_ulonglong),
        ("FirstWinsServerAddress", ctypes.c_void_p),
        ("FirstGatewayAddress", ctypes.c_void_p),
    ]


def _first_ipv4(unicast_pointer: int | None) -> str | None:
    while unicast_pointer:
        unicast = UnicastAddress.from_address(unicast_pointer)
        sockaddr_pointer = unicast.Address.lpSockaddr
        if sockaddr_pointer:
            sockaddr = SockaddrIn.from_address(sockaddr_pointer)
            if sockaddr.family == AF_INET:
                return socket.inet_ntoa(bytes(sockaddr.addr))
        unicast_pointer = unicast.Next
    return None


def read_records() -> list[dict]:
    """Percorre a lista ligada do Windows. Qualquer falha vira OSError (o chamador usa o psutil)."""
    try:
        function = ctypes.WinDLL("iphlpapi.dll").GetAdaptersAddresses
    except (AttributeError, OSError) as exc:
        raise OSError(f"iphlpapi indisponivel: {exc}") from exc
    function.restype = wintypes.ULONG
    size = wintypes.ULONG(START_BUFFER_BYTES)
    for _ in range(MAX_TRIES):
        buffer = ctypes.create_string_buffer(size.value)
        result = function(AF_INET, FLAGS, None, buffer, ctypes.byref(size))
        if result == ERROR_SUCCESS:
            break
        if result != ERROR_BUFFER_OVERFLOW:
            raise OSError(f"GetAdaptersAddresses falhou ({result})")
    else:
        raise OSError("GetAdaptersAddresses: buffer insuficiente")
    records = []
    pointer = ctypes.addressof(buffer)
    while pointer:
        adapter = AdapterAddresses.from_address(pointer)
        records.append(
            {
                "name": adapter.FriendlyName,
                "description": adapter.Description,
                "if_type": adapter.IfType,
                "oper_status": adapter.OperStatus,
                "ipv4": _first_ipv4(adapter.FirstUnicastAddress),
                "has_gateway": bool(adapter.FirstGatewayAddress),
            }
        )
        pointer = adapter.Next
    return records


def read_adapters() -> list[NetInterface]:
    try:
        return interfaces_from_records(read_records())
    except OSError:
        raise
    except Exception as exc:  # ctypes/ValueError em dados inesperados: o chamador tem fallback
        raise OSError(f"leitura das placas falhou: {exc}") from exc
