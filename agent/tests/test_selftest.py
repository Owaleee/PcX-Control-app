"""--self-test: prova que o agente (inclusive o .exe congelado) sobe e le sensores."""

import json

from pcx_agent.main import main
from pcx_agent.sensors.fake import FakeSensorProvider


def test_self_test_demo_writes_ok(tmp_path):
    out = tmp_path / "resultado.json"
    assert main(["--demo", "--self-test", str(out)]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert "cpu" in result["capabilities"]
    assert result["port"] > 0
    assert result["version"]


def test_self_test_reports_failure(tmp_path, monkeypatch):
    def broken(_self):
        raise RuntimeError("sensor quebrado")

    monkeypatch.setattr(FakeSensorProvider, "read", broken)
    out = tmp_path / "resultado.json"
    assert main(["--demo", "--self-test", str(out)]) == 1
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result == {"ok": False, "error": "RuntimeError: sensor quebrado"}


def test_self_test_closes_sensors_once(tmp_path, monkeypatch):
    """O servidor fecha os sensores ao parar; fechar de novo quebra a consulta PDH do Windows."""
    closed = []
    monkeypatch.setattr(FakeSensorProvider, "close", lambda _self: closed.append(1))
    assert main(["--demo", "--self-test", str(tmp_path / "r.json")]) == 0
    assert closed == [1]


def test_self_test_reports_tray_check(tmp_path):
    out = tmp_path / "r.json"
    assert main(["--demo", "--self-test", str(out)]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    import sys

    assert result["tray"] == ("ok" if sys.platform == "win32" else "pulado")


def test_tray_check_failure_fails_self_test(tmp_path, monkeypatch):
    from pcx_agent import selftest

    def broken():
        raise ImportError("pystray._win32")

    monkeypatch.setattr(selftest, "_check_tray", broken)
    monkeypatch.setattr(selftest, "IS_WINDOWS", True)
    out = tmp_path / "r.json"
    assert main(["--demo", "--self-test", str(out)]) == 1
    assert "pystray._win32" in json.loads(out.read_text(encoding="utf-8"))["error"]
