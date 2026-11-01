"""AgentServer: Uvicorn de verdade numa thread, como a bandeja usa."""

import json
import socket
import time
import urllib.request

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from pcx_agent.api.app import build_context
from pcx_agent.config import load_settings
from pcx_agent.sensors.fake import FakeSensorProvider
from pcx_agent.server import AgentServer, PortInUseError


@pytest.fixture
def ctx(tmp_path):
    context = build_context(
        load_settings(data_dir=tmp_path),
        FakeSensorProvider(seed=3),
        idle_interval=0.05,
        active_interval=0.05,
    )
    yield context
    context.db.close()


def _info(port: int) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/info", timeout=5) as resp:
        assert resp.status == 200
        return json.loads(resp.read())


def test_start_serves_info_on_ephemeral_port(ctx):
    server = AgentServer(ctx, "127.0.0.1", 0)
    server.start()
    try:
        assert server.running
        assert server.bound_port > 0
        assert _info(server.bound_port)["agent_id"] == ctx.db.agent_id
    finally:
        server.stop()
    assert not server.running


def test_port_in_use_raises(ctx):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        with pytest.raises(PortInUseError) as info:
            AgentServer(ctx, "127.0.0.1", port).start()
    assert info.value.port == port
    assert str(port) in str(info.value)


def test_stop_frees_port_quickly(ctx, tmp_path):
    token = ctx.pairing.pair("Poco", code=ctx.pairing.new_code(), client_ip="10.0.0.1").token
    server = AgentServer(ctx, "127.0.0.1", 0)
    server.start()
    port = server.bound_port
    with connect(f"ws://127.0.0.1:{port}/v1/stream", open_timeout=5) as ws:
        ws.send(json.dumps({"type": "auth", "token": token}))
        assert json.loads(ws.recv(timeout=5))["type"] == "hello"

        started = time.monotonic()
        server.stop()
        assert time.monotonic() - started < 5
        with pytest.raises(ConnectionClosed):
            for _ in range(50):
                ws.recv(timeout=5)

    again = AgentServer(ctx, "127.0.0.1", port)
    again.start()
    try:
        assert _info(port)["name"]
    finally:
        again.stop()


def test_rejects_oversized_websocket_message(ctx):
    server = AgentServer(ctx, "127.0.0.1", 0)
    server.start()
    try:
        with connect(f"ws://127.0.0.1:{server.bound_port}/v1/stream", open_timeout=5) as ws:
            ws.send("x" * 32 * 1024)
            with pytest.raises(ConnectionClosed) as info:
                ws.recv(timeout=5)
        # 1009 = mensagem grande demais (o limite do servidor), nao o 4401 de auth invalido
        assert info.value.rcvd is not None and info.value.rcvd.code == 1009
        assert _info(server.bound_port)["protocol"] == 1
    finally:
        server.stop()
