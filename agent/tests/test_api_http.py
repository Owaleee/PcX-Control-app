import logging
import time

import pytest

from pcx_agent.session import ActiveSession
from tests.conftest import PASSWORD, bearer, pair_device


async def test_info_is_public_and_has_protocol_1(client, ctx):
    response = await client.get("/v1/info")
    assert response.status_code == 200
    body = response.json()
    assert body["protocol"] == 1
    assert body["agent_id"] == ctx.db.agent_id
    assert body["busy"] is False
    assert {"name", "version"} <= set(body)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
async def test_docs_routes_are_off(client, path):
    assert (await client.get(path)).status_code == 404


async def test_pair_with_password_ok(client):
    response = await client.post(
        "/v1/pair", json={"device_name": "Moto G", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"] and body["device_id"]
    assert body["agent"]["protocol"] == 1


async def test_pair_wrong_password_401_with_attempts_left(client):
    response = await client.post("/v1/pair", json={"device_name": "Moto G", "password": "errada-123"})
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "bad_credentials"
    assert body["attempts_left"] == 4
    assert "Restam 4" in body["message"]


async def test_pair_without_credentials_401(client):
    response = await client.post("/v1/pair", json={"device_name": "Moto G"})
    assert response.status_code == 401
    assert response.json()["code"] == "bad_credentials"


async def test_pair_rate_limited_429_with_retry_after(client):
    for _ in range(5):
        await client.post("/v1/pair", json={"device_name": "Moto G", "password": "errada-123"})
    response = await client.post("/v1/pair", json={"device_name": "Moto G", "password": PASSWORD})
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert 59 <= response.json()["retry_after"] <= 60
    assert int(response.headers["Retry-After"]) in (60, 61)


async def test_pair_code_single_use_410(client, ctx):
    code = ctx.pairing.new_code()
    first = await client.post("/v1/pair", json={"device_name": "A", "code": code})
    second = await client.post("/v1/pair", json={"device_name": "B", "code": code})
    assert first.status_code == 200
    assert second.status_code == 410
    assert second.json()["code"] == "code_invalid_or_expired"


@pytest.mark.parametrize("name", ["", "   ", "x" * 65, "a\x00b"])
async def test_pair_invalid_name_422(client, name):
    response = await client.post("/v1/pair", json={"device_name": name, "password": PASSWORD})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_name"


async def test_pair_malformed_body_422_without_echoing_secrets(client):
    response = await client.post("/v1/pair", json={"password": PASSWORD})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert PASSWORD not in response.text


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}, {"Authorization": "Bearer x"}],
)
async def test_snapshot_requires_token_401(client, headers):
    response = await client.get("/v1/snapshot", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


async def test_snapshot_503_before_first_reading(client, ctx):
    token = await pair_device(client, ctx)
    response = await client.get("/v1/snapshot", headers=bearer(token))
    assert response.status_code == 503
    assert response.json()["code"] == "starting"


async def test_snapshot_with_token_ok(client, ctx):
    token = await pair_device(client, ctx)
    await ctx.sampler.tick()
    response = await client.get("/v1/snapshot", headers=bearer(token))
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["cpu_total"] <= 100
    assert body["gpus"][0]["name"]


async def test_history_ok(client, ctx):
    token = await pair_device(client, ctx)
    ctx.history.record(time.time() - 10, "cpu.total", 30.0, 50.0)
    response = await client.get(
        "/v1/history", params={"metric": "cpu.total", "range": "15m"}, headers=bearer(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["metric"], body["range"]) == ("cpu.total", "15m")
    assert body["points"][0]["avg"] == 30.0 and body["points"][0]["max"] == 50.0


async def test_history_unknown_metric_422(client, ctx):
    token = await pair_device(client, ctx)
    response = await client.get(
        "/v1/history", params={"metric": "nao.existe", "range": "15m"}, headers=bearer(token)
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_metric"


async def test_history_invalid_range_422(client, ctx):
    token = await pair_device(client, ctx)
    response = await client.get(
        "/v1/history", params={"metric": "cpu.total", "range": "2h"}, headers=bearer(token)
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_range"


async def test_delete_me_revokes_and_token_stops_working(client, ctx):
    token = await pair_device(client, ctx)
    assert (await client.delete("/v1/devices/me", headers=bearer(token))).status_code == 204
    assert (await client.get("/v1/snapshot", headers=bearer(token))).status_code == 401
    assert ctx.pairing.list_devices() == []


async def test_snapshot_busy_409_names_active_device(client, ctx):
    first = await pair_device(client, ctx, "Moto G")
    second = await pair_device(client, ctx, "Pixel")
    await ctx.sampler.tick()
    first_id = ctx.pairing.authenticate(first).id
    ctx.sessions.acquire(ActiveSession(first_id, "Moto G", lambda: None), takeover=False)
    busy = await client.get("/v1/snapshot", headers=bearer(second))
    assert busy.status_code == 409
    assert busy.json() == {
        "code": "session_busy",
        "message": busy.json()["message"],
        "active_device": "Moto G",
    }
    assert (await client.get("/v1/snapshot", headers=bearer(first))).status_code == 200
    assert (await client.get("/v1/info")).json()["busy"] is True


async def test_no_secret_in_logs(client, ctx, caplog):
    caplog.set_level(logging.DEBUG)
    code = ctx.pairing.new_code()
    response = await client.post("/v1/pair", json={"device_name": "Moto G", "code": code})
    token = response.json()["token"]
    await client.post("/v1/pair", json={"device_name": "Moto G", "password": "errada-123"})
    await client.get("/v1/snapshot", headers=bearer(token))
    for secret in (code, token, PASSWORD, "errada-123"):
        assert secret not in caplog.text
