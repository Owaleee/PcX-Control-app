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


def test_main_configures_websocket_ping_to_detect_dead_connections(tmp_path, monkeypatch):
    import uvicorn

    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: captured.update(kwargs))
    assert main(["--demo", "--data-dir", str(tmp_path), "--port", "0"]) == 0
    assert captured["ws_ping_interval"] <= 10
    assert captured["ws_ping_timeout"] <= 15
    assert captured["access_log"] is False
