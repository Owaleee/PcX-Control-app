"""O contrato com o app: os arquivos em docs/protocol/fixtures saem do codigo real do agente."""

import json

import pytest

from pcx_agent.contract import FIXTURES_DIR, build_fixtures
from tests.conftest import bearer, pair_device

NAMES = [
    "snapshot_message",
    "hello",
    "info",
    "pair",
    "history",
    "metrics",
    "error_bad_credentials",
    "error_session_busy",
]


def test_every_expected_fixture_is_built():
    assert sorted(build_fixtures()) == sorted(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_fixture_matches_builder(name):
    path = FIXTURES_DIR / f"{name}.json"
    assert path.exists(), f"rode: python tools/write_fixtures.py ({path})"
    built = json.loads(json.dumps(build_fixtures()[name]))
    assert json.loads(path.read_text(encoding="utf-8")) == built


def shape(value):
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


async def test_info_and_pair_fixtures_match_real_responses_shape(client, ctx):
    fixtures = build_fixtures()
    info = (await client.get("/v1/info")).json()
    assert shape(info) == shape(fixtures["info"])
    code = ctx.pairing.new_code()
    paired = (await client.post("/v1/pair", json={"device_name": "Moto G", "code": code})).json()
    assert shape(paired) == shape(fixtures["pair"])
    wrong = await client.post("/v1/pair", json={"device_name": "Moto G", "password": "errada-123"})
    assert shape(wrong.json()) == shape(fixtures["error_bad_credentials"])
    ctx.history.record(1.0e9, "cpu.total", 1.0, 2.0)
    history = await client.get(
        "/v1/history", params={"metric": "cpu.total", "range": "24h"}, headers=bearer(paired["token"])
    )
    assert set(history.json()) == set(fixtures["history"])


async def test_metrics_fixture_matches_snapshot_metrics():
    from pcx_agent.sensors.base import METRIC_NAMES

    metrics = build_fixtures()["metrics"]
    assert sorted(metrics["names"]) == sorted(METRIC_NAMES)
    assert set(metrics["from_snapshot"]) <= set(METRIC_NAMES)


async def test_pair_device_helper_still_works(client, ctx):
    assert await pair_device(client, ctx)
