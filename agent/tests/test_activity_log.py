"""Log de atividade: cada tentativa de pareamento e cada conexao viram uma linha (sem segredos)."""

import logging

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pcx_agent.api.app import build_context, create_app
from pcx_agent.config import load_settings
from pcx_agent.sensors.fake import FakeSensorProvider
from tests.conftest import PASSWORD


def _lines(caplog, logger):
    return [r.getMessage() for r in caplog.records if r.name == logger]


@pytest.mark.parametrize(
    ("body", "resultado", "metodo"),
    [
        ({"password": PASSWORD}, "pareado", "senha"),
        ({"password": "senha-errada"}, "senha_errada", "senha"),
        ({"code": "codigo-que-nao-existe"}, "codigo_invalido", "qr"),
    ],
)
async def test_pair_attempt_is_logged(client, caplog, body, resultado, metodo):
    with caplog.at_level(logging.INFO, logger="pcx_agent.pairing"):
        await client.post("/v1/pair", json={"device_name": "Poco X7 Pro", **body})
    lines = _lines(caplog, "pcx_agent.pairing")
    assert len(lines) == 1
    line = lines[0]
    assert "ip=10.0.0.5" in line
    assert f"metodo={metodo}" in line
    assert f"resultado={resultado}" in line
    assert "'Poco X7 Pro'" in line
    for secret in body.values():
        assert secret not in line


async def test_qr_pairing_logs_without_the_code(client, ctx, caplog):
    code = ctx.pairing.new_code()
    with caplog.at_level(logging.INFO, logger="pcx_agent.pairing"):
        await client.post("/v1/pair", json={"device_name": "Moto", "code": code})
    line = _lines(caplog, "pcx_agent.pairing")[0]
    assert "metodo=qr" in line and "resultado=pareado" in line
    assert code not in line


async def test_blocked_and_invalid_name_are_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="pcx_agent.pairing"):
        await client.post("/v1/pair", json={"device_name": " ", "password": PASSWORD})
        for _ in range(6):
            await client.post("/v1/pair", json={"device_name": "X", "password": "errada"})
    lines = _lines(caplog, "pcx_agent.pairing")
    assert any("resultado=nome_invalido" in line for line in lines)
    assert any("resultado=bloqueado" in line for line in lines)


async def test_device_name_with_newline_stays_one_line(client, caplog):
    with caplog.at_level(logging.INFO, logger="pcx_agent.pairing"):
        await client.post("/v1/pair", json={"device_name": "a\nb", "password": PASSWORD})
    assert all("\n" not in line for line in _lines(caplog, "pcx_agent.pairing"))


@pytest.fixture
def live(tmp_path):
    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider(seed=2),
                        idle_interval=0.05, active_interval=0.05, flush_interval=0.05)
    ctx.passwords.set_password(PASSWORD)
    with TestClient(create_app(ctx)) as client:
        yield client, ctx
    ctx.db.close()


def test_stream_connect_and_disconnect_are_logged(live, caplog):
    client, ctx = live
    token = ctx.pairing.pair("Poco", password=PASSWORD, client_ip="10.0.0.1").token
    with (
        caplog.at_level(logging.INFO, logger="pcx_agent.stream"),
        client.websocket_connect("/v1/stream") as ws,
    ):
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "hello"
    lines = _lines(caplog, "pcx_agent.stream")
    assert any("conectado" in line and "'Poco'" in line for line in lines)
    assert any("desconectado" in line and "'Poco'" in line for line in lines)
    assert all(token not in line for line in lines)


def test_stream_invalid_token_is_logged_with_ip(live, caplog):
    client, _ctx = live
    with (
        caplog.at_level(logging.INFO, logger="pcx_agent.stream"),
        client.websocket_connect("/v1/stream") as ws,
    ):
        ws.send_json({"type": "auth", "token": "token-que-nao-existe-1234567890"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    lines = _lines(caplog, "pcx_agent.stream")
    assert any("token inválido" in line and "ip=" in line for line in lines)
    assert all("token-que-nao-existe" not in line for line in lines)


def test_stream_busy_and_takeover_are_logged(live, caplog):
    client, ctx = live
    first = ctx.pairing.pair("Poco", password=PASSWORD, client_ip="10.0.0.1").token
    second = ctx.pairing.pair("Moto", password=PASSWORD, client_ip="10.0.0.2").token
    with (
        caplog.at_level(logging.INFO, logger="pcx_agent.stream"),
        client.websocket_connect("/v1/stream") as active,
    ):
        active.send_json({"type": "auth", "token": first})
        active.receive_json()
        with client.websocket_connect("/v1/stream") as other:
            other.send_json({"type": "auth", "token": second})
            with pytest.raises(WebSocketDisconnect):
                other.receive_json()
        with client.websocket_connect("/v1/stream") as other:
            other.send_json({"type": "auth", "token": second, "takeover": True})
            assert other.receive_json()["type"] == "hello"
    lines = _lines(caplog, "pcx_agent.stream")
    assert any("ocupado" in line and "'Moto'" in line and "'Poco'" in line for line in lines)
    assert any("assumiu" in line and "'Moto'" in line for line in lines)
