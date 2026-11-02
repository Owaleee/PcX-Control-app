"""AgentController: tudo o que a bandeja faz, sem tkinter."""

import time
from urllib.parse import parse_qs, urlparse

import pytest

from pcx_agent.api.app import build_context
from pcx_agent.auth.pairing import PairError
from pcx_agent.config import load_settings
from pcx_agent.controller import (
    NO_NETWORK_WARNING,
    AgentController,
    PasswordInputError,
    format_last_used,
)
from pcx_agent.sensors.fake import FakeSensorProvider
from pcx_agent.session import ActiveSession

NOW = 2_000_000_000.0


@pytest.fixture
def ctx(tmp_path):
    context = build_context(load_settings(data_dir=tmp_path), FakeSensorProvider(seed=1))
    yield context
    context.db.close()


def make(ctx, host="192.168.0.10", interface="Ethernet", category=None):
    return AgentController(
        ctx,
        8765,
        address_lookup=lambda: (host, interface),
        category_lookup=lambda _name: category,
        now=lambda: NOW,
    )


def test_set_password_rejects_mismatch(ctx):
    with pytest.raises(PasswordInputError) as info:
        make(ctx).set_password("senha-boa-1", "senha-boa-2")
    assert info.value.message == "As senhas não são iguais."
    assert not ctx.passwords.is_set()


def test_set_password_rejects_short(ctx):
    with pytest.raises(PasswordInputError) as info:
        make(ctx).set_password("curta", "curta")
    assert info.value.message == "A senha precisa ter pelo menos 8 caracteres."


def test_first_run_flag_clears_after_password(ctx):
    controller = make(ctx)
    assert controller.needs_first_run()
    controller.set_password("senha-boa-1", "senha-boa-1")
    assert not controller.needs_first_run()
    assert ctx.passwords.verify("senha-boa-1")


def test_start_pairing_builds_uri_with_lan_host(ctx):
    info = make(ctx).start_pairing()
    query = parse_qs(urlparse(info.uri).query)
    assert info.uri.startswith("pcx://pair?v=1")
    assert query["h"] == ["192.168.0.10"]
    assert query["p"] == ["8765"]
    assert query["c"] == [info.code]
    assert query["id"] == [ctx.db.agent_id]
    assert (info.host, info.port, info.interface) == ("192.168.0.10", 8765, "Ethernet")
    assert info.warning is None
    assert info.expires_at == NOW + ctx.pairing.code_ttl_s == NOW + 300


def test_start_pairing_warns_without_network(ctx):
    info = make(ctx, host="127.0.0.1").start_pairing()
    assert info.warning == NO_NETWORK_WARNING
    assert info.warning == (
        "Não encontrei a rede deste PC. Conecte-o ao Wi-Fi ou ao cabo e gere outro código."
    )


def test_new_pairing_invalidates_previous_code(ctx):
    controller = make(ctx)
    first = controller.start_pairing()
    controller.start_pairing()
    with pytest.raises(PairError) as info:
        ctx.pairing.pair("Moto", code=first.code, client_ip="10.0.0.1")
    assert info.value.kind == "code_invalid_or_expired"


def _pair(ctx, name, ip="10.0.0.1"):
    return ctx.pairing.pair(name, code=ctx.pairing.new_code(), client_ip=ip).device_id


def test_devices_lists_active_first(ctx):
    controller = make(ctx)
    old = _pair(ctx, "Antigo")
    ativo = _pair(ctx, "Poco X7 Pro")
    ctx.sessions.acquire(ActiveSession(ativo, "Poco X7 Pro", evict=lambda: None), False)
    rows = controller.devices()
    assert [(r.id, r.active) for r in rows] == [(ativo, True), (old, False)]
    assert all(isinstance(r.last_used, str) and r.last_used for r in rows)


def test_revoke_closes_active_session(ctx):
    controller = make(ctx)
    device = _pair(ctx, "Poco")
    revoked = []
    session = ActiveSession(device, "Poco", evict=lambda: None, on_revoke=lambda: revoked.append(1))
    ctx.sessions.acquire(session, False)
    controller.revoke(device)
    assert revoked == [1]
    assert controller.devices() == []
    assert not ctx.sessions.has_active()


def test_revoke_all_removes_every_device(ctx):
    controller = make(ctx)
    _pair(ctx, "A")
    _pair(ctx, "B")
    controller.revoke_all()
    assert controller.devices() == []


def test_status_text_reflects_session(ctx):
    controller = make(ctx)
    assert controller.status_text() == "PcX Control: aguardando celular"
    device = _pair(ctx, "Poco X7 Pro")
    ctx.sessions.acquire(ActiveSession(device, "Poco X7 Pro", evict=lambda: None), False)
    assert controller.status_text() == "PcX Control: conectado a Poco X7 Pro"


def test_on_paired_called_with_device_name(ctx):
    controller = make(ctx)
    names = []
    controller.on_paired = names.append
    _pair(ctx, "Poco X7 Pro")
    assert names == ["Poco X7 Pro"]


def _local(y, mo, d, h, mi):
    return time.mktime((y, mo, d, h, mi, 0, 0, 0, -1))


@pytest.mark.parametrize(
    ("ts", "expected"),
    [
        (_local(2026, 11, 1, 17, 59) + 30, "agora"),
        (_local(2026, 11, 1, 17, 48), "há 12 min"),
        (_local(2026, 11, 1, 9, 5), "hoje às 09:05"),
        (_local(2026, 10, 31, 21, 14), "ontem às 21:14"),
        (_local(2026, 10, 12, 8, 0), "12/10/2026"),
    ],
)
def test_format_last_used(ts, expected):
    assert format_last_used(ts, _local(2026, 11, 1, 18, 0)) == expected


def test_format_last_used_future_is_now():
    now = _local(2026, 11, 1, 18, 0)
    assert format_last_used(now + 5, now) == "agora"


def test_default_address_lookup_ignores_vpn(ctx, monkeypatch):
    """Sem injecao, o controlador usa network.lan_address (que ignora VPNs)."""
    import pcx_agent.controller as controller_module

    monkeypatch.setattr(controller_module, "lan_address", lambda: ("192.168.18.22", "Ethernet"))
    info = AgentController(ctx, 8765, now=lambda: NOW).start_pairing()
    assert info.host == "192.168.18.22"
    assert info.interface == "Ethernet"
