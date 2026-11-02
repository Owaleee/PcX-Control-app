import re
import sys
import time

import pytest
from starlette.testclient import TestClient

from pcx_agent.api.app import build_context, create_app
from pcx_agent.config import load_settings
from pcx_agent.main import main
from pcx_agent.sensors.fake import FakeSensorProvider

IDLE, ACTIVE = 0.2, 0.05


def test_full_flow_with_fake_provider(tmp_path):
    ctx = build_context(
        load_settings(data_dir=tmp_path),
        FakeSensorProvider(seed=3),
        idle_interval=IDLE,
        active_interval=ACTIVE,
        flush_interval=0.05,
    )
    try:
        with TestClient(create_app(ctx)) as client:
            code = ctx.pairing.new_code()
            paired = client.post("/v1/pair", json={"device_name": "Moto G", "code": code})
            assert paired.status_code == 200
            headers = {"Authorization": f"Bearer {paired.json()['token']}"}
            assert ctx.sampler.current_interval() == IDLE

            with client.websocket_connect("/v1/stream") as ws:
                ws.send_json({"type": "auth", "token": paired.json()["token"]})
                assert ws.receive_json()["type"] == "hello"
                assert ws.receive_json()["type"] == "snapshot"
                assert ws.receive_json()["type"] == "snapshot"
                assert ctx.sampler.current_interval() == ACTIVE

            for _ in range(100):
                if not client.get("/v1/info").json()["busy"]:
                    break
                time.sleep(0.02)
            assert ctx.sampler.current_interval() == IDLE

            points = []
            for _ in range(100):
                response = client.get(
                    "/v1/history", params={"metric": "cpu.total", "range": "15m"}, headers=headers
                )
                points = response.json()["points"]
                if points:
                    break
                time.sleep(0.02)
            assert points and all(0 <= p["avg"] <= 100 for p in points)
    finally:
        ctx.db.close()


def test_cli_demo_prints_pairing_code(tmp_path, capsys):
    exit_code = main(["--demo", "--data-dir", str(tmp_path), "--port", "0", "--dry-run"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert re.search(r"Código de pareamento: \S{16,}", out)
    assert "demo-password" in out
    assert (tmp_path / "pcx.db").exists()


def test_cli_demo_without_data_dir_uses_temp_folder(capsys):
    assert main(["--demo", "--port", "0", "--dry-run"]) == 0
    assert "pcx-demo-" in capsys.readouterr().out


@pytest.mark.skipif(sys.platform == "win32", reason="so vale fora do Windows")
def test_cli_without_demo_on_linux_exits_2(tmp_path, capsys):
    assert main(["--data-dir", str(tmp_path), "--dry-run"]) == 2
    assert "--demo" in capsys.readouterr().err


def test_real_uvicorn_server_accepts_websocket(tmp_path):
    """Sobe um Uvicorn de verdade: o TestClient nao exige o pacote de WebSocket do servidor."""
    import json
    import threading

    import uvicorn
    from websockets.sync.client import connect

    ctx = build_context(
        load_settings(data_dir=tmp_path),
        FakeSensorProvider(seed=4),
        idle_interval=0.05,
        active_interval=0.05,
    )
    token = ctx.pairing.pair("Moto G", code=ctx.pairing.new_code(), client_ip="10.0.0.1").token
    server = uvicorn.Server(
        uvicorn.Config(create_app(ctx), host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        with connect(f"ws://127.0.0.1:{port}/v1/stream", open_timeout=5) as ws:
            ws.send(json.dumps({"type": "auth", "token": token}))
            assert json.loads(ws.recv(timeout=5))["type"] == "hello"
            assert json.loads(ws.recv(timeout=5))["type"] == "snapshot"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        ctx.db.close()


def test_server_config_pings_websocket_to_detect_dead_connections():
    from pcx_agent.server import uvicorn_config

    config = uvicorn_config(object(), "127.0.0.1", 0)
    assert config.ws_ping_interval <= 10
    assert config.ws_ping_timeout <= 15
    assert config.access_log is False


def test_demo_console_uses_agent_server(tmp_path, monkeypatch, capsys):
    import pcx_agent.main as cli

    calls = []

    class FakeServer:
        def __init__(self, ctx, host, port):
            calls.append(("init", host, port))

        def start(self):
            calls.append("start")

        def stop(self):
            calls.append("stop")

    monkeypatch.setattr(cli, "AgentServer", FakeServer)
    monkeypatch.setattr(cli, "_wait_until_interrupted", lambda: calls.append("wait"))
    assert main(["--demo", "--data-dir", str(tmp_path), "--port", "9123"]) == 0
    assert calls == [("init", "0.0.0.0", 9123), "start", "wait", "stop"]
    assert "pcx://pair?v=1" in capsys.readouterr().out


def test_console_reports_port_in_use(tmp_path, capsys):
    import socket

    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        code = main(["--demo", "--data-dir", str(tmp_path), "--host", "127.0.0.1",
                     "--port", str(port)])
    assert code == 1
    assert f"A porta {port} já está em uso" in capsys.readouterr().err


def test_console_warns_without_network(tmp_path, monkeypatch, capsys):
    import pcx_agent.main as cli

    monkeypatch.setattr(cli, "lan_address", lambda: ("127.0.0.1", None))
    assert main(["--demo", "--data-dir", str(tmp_path), "--port", "0", "--dry-run"]) == 0
    assert "Não encontrei a rede deste PC" in capsys.readouterr().out


def test_busy_close_code_survives_long_device_name(tmp_path):
    """No Uvicorn real o motivo do fechamento e limitado a 123 bytes; o codigo 4423 deve chegar."""
    import json
    import threading

    import uvicorn
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    ctx = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider(seed=5))
    long_name = "ç" * 62  # 124 bytes em UTF-8
    first = ctx.pairing.pair(long_name, code=ctx.pairing.new_code(), client_ip="10.0.0.1").token
    second = ctx.pairing.pair("Pixel", code=ctx.pairing.new_code(), client_ip="10.0.0.2").token
    server = uvicorn.Server(
        uvicorn.Config(create_app(ctx), host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.02)
        port = server.servers[0].sockets[0].getsockname()[1]
        url = f"ws://127.0.0.1:{port}/v1/stream"
        with connect(url, open_timeout=5) as active:
            active.send(json.dumps({"type": "auth", "token": first}))
            assert json.loads(active.recv(timeout=5))["type"] == "hello"
            with connect(url, open_timeout=5) as other:
                other.send(json.dumps({"type": "auth", "token": second}))
                with pytest.raises(ConnectionClosed) as info:
                    other.recv(timeout=5)
                assert info.value.rcvd is not None
                assert info.value.rcvd.code == 4423
                assert info.value.rcvd.reason.startswith("ç")
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        ctx.db.close()
