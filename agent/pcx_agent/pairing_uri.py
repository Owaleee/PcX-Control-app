"""URI e QR code de pareamento (pcx://pair?...), lidos pela camera do app."""

import io
import socket
from typing import TextIO
from urllib.parse import quote

import qrcode

URI_VERSION = 1


def local_ipv4() -> str:
    """IPv4 da placa de rede usada para sair da maquina (nao envia nenhum pacote)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.254.254.254", 1))
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def pairing_uri(agent_id: str, host: str, port: int, code: str) -> str:
    def q(value: object) -> str:
        return quote(str(value), safe="")

    return (
        f"pcx://pair?v={URI_VERSION}&id={q(agent_id)}&h={q(host)}&p={q(port)}&c={q(code)}"
    )


def qr_text(uri: str) -> str:
    qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(uri)
    out = io.StringIO()
    qr.print_ascii(out=out, invert=True)
    return out.getvalue()


def print_pairing(out: TextIO, code: str, uri: str) -> None:
    out.write(f"Código de pareamento: {code} (vale 5 minutos)\n")
    out.write(f"Endereço de pareamento: {uri}\n")
    try:
        out.write(qr_text(uri))
        out.flush()
    except UnicodeEncodeError:
        out.write(
            "Este terminal não consegue mostrar o QR code. "
            "Use o código acima ou o pareamento por IP e senha.\n"
        )
