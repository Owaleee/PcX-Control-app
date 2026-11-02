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
