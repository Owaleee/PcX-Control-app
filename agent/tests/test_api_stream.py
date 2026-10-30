import json
import time

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pcx_agent.api.app import build_context, create_app
from pcx_agent.api.stream import StreamHub, _Slot
from pcx_agent.config import load_settings
from pcx_agent.sensors.fake import FakeSensorProvider
from tests.conftest import PASSWORD
from tests.test_fake_sensors import make_snapshot

FAST = {"idle_interval": 0.05, "active_interval": 0.05, "flush_interval": 0.05}


@pytest.fixture
def live(tmp_path):
    opened = []

    def make(auth_timeout_s: float = 5.0, session_timeout_s: float = 15.0):
        settings = load_settings(data_dir=tmp_path / f"d{len(opened)}")
        ctx = build_context(
            settings, FakeSensorProvider(seed=2), session_timeout_s=session_timeout_s, **FAST
        )
        ctx.passwords.set_password(PASSWORD)
        client = TestClient(create_app(ctx, auth_timeout_s=auth_timeout_s))
        client.__enter__()
        opened.append((client, ctx))
        return client, ctx

    yield make
    for client, ctx in opened:
        client.__exit__(None, None, None)
        ctx.db.close()


def token_for(ctx, name="Moto G", ip="10.0.0.1"):
    result = ctx.pairing.pair(name, password=PASSWORD, client_ip=ip)
    return result.token, result.device_id


def auth(token, takeover=False):
    return json.dumps({"type": "auth", "token": token, "takeover": takeover})


def close_code(ws) -> int:
    """Le mensagens ate o servidor fechar e devolve o codigo de fechamento."""
    with pytest.raises(WebSocketDisconnect) as info:
        for _ in range(200):
            ws.receive_json()
    return info.value.code


def test_auth_then_hello_then_snapshot(live):
    client, ctx = live()
    token, _ = token_for(ctx)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["protocol"] == 1
        assert hello["agent"]["id"] == ctx.db.agent_id
        assert "cpu" in hello["capabilities"]
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["seq"] >= 1
        assert 0 <= snapshot["data"]["cpu_total"] <= 100
        assert snapshot["t"]


def test_invalid_token_closes_4401(live):
    client, _ = live()
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth("token-falso"))
        assert close_code(ws) == 4401


def test_revoked_token_cannot_connect(live):
    client, ctx = live()
    token, device_id = token_for(ctx)
    ctx.pairing.revoke(device_id)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        assert close_code(ws) == 4401


def test_no_auth_in_time_closes_4408(live):
    client, _ = live(auth_timeout_s=0.2)
    with client.websocket_connect("/v1/stream") as ws:
        assert close_code(ws) == 4408


def test_busy_without_takeover_closes_4423(live):
    client, ctx = live()
    first, _ = token_for(ctx, "Moto G", "10.0.0.1")
    second, _ = token_for(ctx, "Pixel", "10.0.0.2")
    with client.websocket_connect("/v1/stream") as ws1:
        ws1.send_text(auth(first))
        assert ws1.receive_json()["type"] == "hello"
        with client.websocket_connect("/v1/stream") as ws2:
            ws2.send_text(auth(second))
            with pytest.raises(WebSocketDisconnect) as info:
                ws2.receive_json()
            assert info.value.code == 4423
            assert "Moto G" in info.value.reason


def test_takeover_closes_old_with_4409_and_new_receives_snapshots(live):
    client, ctx = live()
    first, _ = token_for(ctx, "Moto G", "10.0.0.1")
    second, _ = token_for(ctx, "Pixel", "10.0.0.2")
    with client.websocket_connect("/v1/stream") as ws1:
        ws1.send_text(auth(first))
        assert ws1.receive_json()["type"] == "hello"
        with client.websocket_connect("/v1/stream") as ws2:
            ws2.send_text(auth(second, takeover=True))
            assert ws2.receive_json()["type"] == "hello"
            assert ws2.receive_json()["type"] == "snapshot"
            assert close_code(ws1) == 4409


@pytest.mark.parametrize(
    "payload",
    [
        "isto nao e json",
        "{}",
        '{"type": "ping"}',
        '{"type": "auth"}',
        '{"type": "auth", "token": 123}',
        "[1, 2, 3]",
        "x" * 10_000,
    ],
)
def test_garbage_first_message_closes_without_crashing(live, payload):
    client, _ = live()
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(payload)
        assert close_code(ws) == 4401
    assert client.get("/v1/info").status_code == 200


def test_binary_first_message_closes_without_crashing(live):
    client, _ = live()
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_bytes(b"\x00\x01\x02")
        assert close_code(ws) == 4401
    assert client.get("/v1/info").status_code == 200


async def test_slot_keeps_only_the_latest_snapshot():
    slot = _Slot()
    for seq in (1, 2, 3):
        slot.put(seq, make_snapshot(cpu_total=float(seq)))
    seq, snapshot = await slot.get()
    assert (seq, snapshot.cpu_total) == (3, 3.0)


def test_hub_publish_without_listener_only_counts():
    hub = StreamHub()
    hub.publish(make_snapshot())
    hub.publish(make_snapshot())
    assert hub.seq == 2 and hub.slot is None


async def test_hub_feeds_the_active_slot_with_increasing_seq():
    hub = StreamHub()
    hub.slot = _Slot()
    hub.publish(make_snapshot(cpu_total=1.0))
    hub.publish(make_snapshot(cpu_total=2.0))
    seq, snapshot = await hub.slot.get()
    assert (seq, snapshot.cpu_total) == (2, 2.0)


def test_disconnect_releases_session(live):
    client, ctx = live()
    token, _ = token_for(ctx)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        assert ws.receive_json()["type"] == "hello"
        assert client.get("/v1/info").json()["busy"] is True
    for _ in range(100):
        if client.get("/v1/info").json()["busy"] is False:
            break
        time.sleep(0.02)
    assert client.get("/v1/info").json()["busy"] is False


def test_same_device_reconnect_keeps_new_session(live):
    client, ctx = live()
    token, _ = token_for(ctx)
    with client.websocket_connect("/v1/stream") as old:
        old.send_text(auth(token))
        assert old.receive_json()["type"] == "hello"
        with client.websocket_connect("/v1/stream") as new:
            new.send_text(auth(token))
            assert new.receive_json()["type"] == "hello"
            assert close_code(old) == 1001
            assert new.receive_json()["type"] == "snapshot"
            assert client.get("/v1/info").json()["busy"] is True


def test_listening_only_client_stays_connected_past_session_timeout(live):
    """O spec nao exige mensagens do celular: quem so escuta nao pode ser derrubado."""
    client, ctx = live(session_timeout_s=0.3)
    token, _ = token_for(ctx)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        assert ws.receive_json()["type"] == "hello"
        deadline = time.monotonic() + 1.6
        count = 0
        while time.monotonic() < deadline:
            assert ws.receive_json()["type"] == "snapshot"
            count += 1
        assert count > 10
        assert client.get("/v1/info").json()["busy"] is True


def test_client_messages_are_accepted_and_ignored(live):
    client, ctx = live()
    token, _ = token_for(ctx)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        assert ws.receive_json()["type"] == "hello"
        ws.send_text('{"type": "ping"}')
        ws.send_text("lixo qualquer")
        assert ws.receive_json()["type"] == "snapshot"
        assert ws.receive_json()["type"] == "snapshot"


def test_revoking_active_device_closes_stream_with_4401_and_frees_session(live):
    client, ctx = live()
    token, device_id = token_for(ctx)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        assert ws.receive_json()["type"] == "hello"
        started = time.monotonic()
        ctx.pairing.revoke(device_id)  # como a bandeja faria, de outra thread
        assert close_code(ws) == 4401
        assert time.monotonic() - started < 2
    assert client.get("/v1/info").json()["busy"] is False


def test_revoke_all_closes_stream(live):
    client, ctx = live()
    token, _ = token_for(ctx)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        assert ws.receive_json()["type"] == "hello"
        ctx.pairing.revoke_all()
        assert close_code(ws) == 4401


def test_revoking_another_device_keeps_stream(live):
    client, ctx = live()
    token, _ = token_for(ctx, "Moto G", "10.0.0.1")
    _, other_id = token_for(ctx, "Pixel", "10.0.0.2")
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(auth(token))
        assert ws.receive_json()["type"] == "hello"
        ctx.pairing.revoke(other_id)
        assert ws.receive_json()["type"] == "snapshot"
        assert ws.receive_json()["type"] == "snapshot"
