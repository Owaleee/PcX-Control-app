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
