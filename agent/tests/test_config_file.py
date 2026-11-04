"""config.json na pasta de dados: porta configuravel, sem travar com arquivo ruim."""

import json
import logging

import pytest

from pcx_agent.config import DEFAULT_PORT, load_settings


def test_creates_default_config_file(tmp_path):
    settings = load_settings(data_dir=tmp_path)
    assert settings.config_path == tmp_path / "config.json"
    assert json.loads(settings.config_path.read_text(encoding="utf-8")) == {"port": DEFAULT_PORT}
    assert settings.port == DEFAULT_PORT


def test_log_dir_is_inside_data_dir(tmp_path):
    assert load_settings(data_dir=tmp_path).log_dir == tmp_path / "logs"


def test_config_json_sets_port(tmp_path):
    (tmp_path / "config.json").write_text('{"port": 9000}', encoding="utf-8")
    assert load_settings(data_dir=tmp_path).port == 9000


@pytest.mark.parametrize("value", ["abc", 0, 70000, True, 80.5, None])
def test_invalid_port_falls_back(tmp_path, caplog, value):
    (tmp_path / "config.json").write_text(json.dumps({"port": value}), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="pcx_agent.config"):
        settings = load_settings(data_dir=tmp_path)
    assert settings.port == DEFAULT_PORT
    assert any("porta" in r.getMessage().lower() for r in caplog.records)


def test_malformed_json_falls_back_and_is_kept(tmp_path, caplog):
    path = tmp_path / "config.json"
    path.write_text("{port:", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="pcx_agent.config"):
        settings = load_settings(data_dir=tmp_path)
    assert settings.port == DEFAULT_PORT
    assert path.read_text(encoding="utf-8") == "{port:"
    assert caplog.records


def test_config_that_is_not_an_object_falls_back(tmp_path):
    (tmp_path / "config.json").write_text("[8765]", encoding="utf-8")
    assert load_settings(data_dir=tmp_path).port == DEFAULT_PORT


def test_cli_port_overrides_config(tmp_path):
    (tmp_path / "config.json").write_text('{"port": 9000}', encoding="utf-8")
    assert load_settings(data_dir=tmp_path, port=9100).port == 9100


def test_config_saved_with_bom_is_read(tmp_path):
    """O Bloco de Notas pode salvar "UTF-8 com BOM"; a porta do usuario continua valendo."""
    (tmp_path / "config.json").write_bytes(b'\xef\xbb\xbf{"port": 9001}')
    assert load_settings(data_dir=tmp_path).port == 9001


def test_save_port_keeps_other_keys(tmp_path):
    from pcx_agent.config import save_port

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"port": 8765, "outra": "coisa"}), encoding="utf-8")
    assert save_port(path, 8770) is True
    assert json.loads(path.read_text(encoding="utf-8")) == {"port": 8770, "outra": "coisa"}


def test_save_port_unreadable_returns_false(tmp_path):
    from pcx_agent.config import save_port

    path = tmp_path / "config.json"
    path.write_text("{lixo", encoding="utf-8")
    assert save_port(path, 8770) is False
    assert path.read_text(encoding="utf-8") == "{lixo"


def test_save_port_read_only_folder_returns_false(tmp_path, monkeypatch):
    from pathlib import Path

    from pcx_agent.config import save_port

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"port": 8765}), encoding="utf-8")

    def refuse(self, *args, **kwargs):
        raise PermissionError("somente leitura")

    monkeypatch.setattr(Path, "write_text", refuse)
    monkeypatch.setattr(Path, "replace", refuse)
    assert save_port(path, 8770) is False
    assert json.loads(path.read_text(encoding="utf-8")) == {"port": 8765}


def test_announced_protocol_ignores_env_outside_demo():
    from pcx_agent.config import announced_protocol

    assert announced_protocol(False, {"PCX_TEST_PROTOCOL": "2"}) == 1


@pytest.mark.parametrize(("raw", "expected"), [("2", 2), (" 3 ", 3), ("", 1), ("x", 1), ("0", 1), ("-2", 1)])
def test_announced_protocol_in_demo(raw, expected):
    from pcx_agent.config import announced_protocol

    assert announced_protocol(True, {"PCX_TEST_PROTOCOL": raw}) == expected
    assert announced_protocol(True, {}) == 1


def test_settings_protocol_reaches_info_and_hello(tmp_path):
    from dataclasses import replace

    from starlette.testclient import TestClient

    from pcx_agent.api.app import build_context, create_app
    from pcx_agent.sensors.fake import FakeSensorProvider

    settings = replace(load_settings(data_dir=tmp_path), protocol=2)
    ctx = build_context(settings, FakeSensorProvider(seed=1))
    try:
        with TestClient(create_app(ctx)) as client:
            assert client.get("/v1/info").json()["protocol"] == 2
            paired = client.post("/v1/pair", json={"device_name": "X", "code": ctx.pairing.new_code()}).json()
            assert paired["agent"]["protocol"] == 2
            with client.websocket_connect("/v1/stream") as ws:
                ws.send_json({"type": "auth", "token": paired["token"]})
                assert ws.receive_json()["protocol"] == 2
    finally:
        ctx.db.close()
