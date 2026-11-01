import io
import re
from urllib.parse import parse_qs, urlsplit

from pcx_agent import pairing_uri as module
from pcx_agent.main import main
from pcx_agent.pairing_uri import local_ipv4, pairing_uri, print_pairing, qr_text

AGENT = "8e3c523e-8ee9-4e80-b25f-411510ac887f"


def fields(uri: str) -> dict[str, str]:
    parts = urlsplit(uri)
    assert (parts.scheme, parts.netloc) == ("pcx", "pair")
    return {key: values[0] for key, values in parse_qs(parts.query).items()}


def test_uri_has_all_fields_and_roundtrips():
    uri = pairing_uri(AGENT, "192.168.0.10", 8765, "MnCHP7Ky8pv1RI7XrybKIw")
    assert uri.startswith("pcx://pair?v=1&")
    assert fields(uri) == {
        "v": "1",
        "id": AGENT,
        "h": "192.168.0.10",
        "p": "8765",
        "c": "MnCHP7Ky8pv1RI7XrybKIw",
    }


def test_uri_escapes_code():
    code = "a-b_c+d/e="
    assert fields(pairing_uri(AGENT, "10.0.0.1", 8765, code))["c"] == code


def test_local_ipv4_is_dotted_quad():
    assert re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", local_ipv4())


def test_local_ipv4_falls_back_on_error(monkeypatch):
    class Broken:
        def __init__(self, *args, **kwargs):
            raise OSError("sem rede")

    monkeypatch.setattr(module.socket, "socket", Broken)
    assert local_ipv4() == "127.0.0.1"


def test_qr_text_has_many_lines():
    assert len(qr_text("pcx://pair?v=1").splitlines()) > 10


def test_print_pairing_falls_back_when_terminal_cannot_show_blocks():
    raw = io.BytesIO()
    out = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    print_pairing(out, "CODIGO123", "pcx://pair?v=1&c=CODIGO123")
    out.flush()
    text = raw.getvalue().decode("cp1252")
    assert "CODIGO123" in text
    assert "pcx://pair?v=1" in text
    assert "QR code" in text  # mensagem explicando que o QR nao pode ser exibido


def test_cli_prints_uri_and_qr(tmp_path, capsys):
    assert main(["--demo", "--data-dir", str(tmp_path), "--port", "0", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "pcx://pair?v=1&" in out
    assert len(out.splitlines()) > 15


def test_qr_uses_explicit_host(tmp_path, capsys):
    main(["--demo", "--data-dir", str(tmp_path), "--host", "127.0.0.1", "--dry-run"])
    uri = re.search(r"pcx://pair\S+", capsys.readouterr().out).group(0)
    assert fields(uri)["h"] == "127.0.0.1"
    assert fields(uri)["p"] == "8765"
