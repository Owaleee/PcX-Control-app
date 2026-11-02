"""Logica da bandeja, sem tkinter: as janelas so chamam este controlador."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from pcx_agent.api.app import AppContext
from pcx_agent.auth.pairing import Device
from pcx_agent.auth.passwords import MIN_LENGTH
from pcx_agent.pairing_uri import local_ipv4, pairing_uri

LOOPBACK = "127.0.0.1"
NO_NETWORK_WARNING = (
    "Não encontrei a rede deste PC. Conecte-o ao Wi-Fi ou ao cabo e gere outro código."
)
MISMATCH_MESSAGE = "As senhas não são iguais."
SHORT_MESSAGE = f"A senha precisa ter pelo menos {MIN_LENGTH} caracteres."


class PasswordInputError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class PairingInfo:
    code: str
    uri: str
    host: str
    port: int
    expires_at: float
    warning: str | None


@dataclass(frozen=True)
class DeviceRow:
    id: str
    name: str
    last_used: str
    active: bool


def format_last_used(ts: float, now: float) -> str:
    elapsed = now - ts
    if elapsed < 60:
        return "agora"
    if elapsed < 3600:
        return f"há {int(elapsed // 60)} min"
    when, today = time.localtime(ts), time.localtime(now)
    if when[:3] == today[:3]:
        return time.strftime("hoje às %H:%M", when)
    midnight = time.mktime((*today[:3], 0, 0, 0, 0, 0, -1))
    yesterday = time.localtime(midnight - 43200)  # meio-dia de ontem (seguro no horario de verao)
    if when[:3] == yesterday[:3]:
        return time.strftime("ontem às %H:%M", when)
    return time.strftime("%d/%m/%Y", when)


class AgentController:
    def __init__(
        self,
        ctx: AppContext,
        port: int,
        *,
        host_lookup: Callable[[], str] = local_ipv4,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._ctx = ctx
        self._port = port
        self._host_lookup = host_lookup
        self._now = now
        self.on_paired: Callable[[str], None] | None = None
        ctx.pairing.on_pair = self._handle_pair

    def _handle_pair(self, device: Device) -> None:
        if self.on_paired is not None:
            self.on_paired(device.name)

    def needs_first_run(self) -> bool:
        return not self._ctx.passwords.is_set()

    def set_password(self, new: str, confirm: str) -> None:
        if new != confirm:
            raise PasswordInputError(MISMATCH_MESSAGE)
        if len(new) < MIN_LENGTH:
            raise PasswordInputError(SHORT_MESSAGE)
        self._ctx.passwords.set_password(new)

    def start_pairing(self) -> PairingInfo:
        code = self._ctx.pairing.new_code()
        host = self._host_lookup()
        return PairingInfo(
            code=code,
            uri=pairing_uri(self._ctx.db.agent_id, host, self._port, code),
            host=host,
            port=self._port,
            expires_at=self._now() + self._ctx.pairing.code_ttl_s,
            warning=NO_NETWORK_WARNING if host == LOOPBACK else None,
        )

    def devices(self) -> list[DeviceRow]:
        active = self._ctx.sessions.active()
        active_id = active.device_id if active is not None else None
        now = self._now()
        devices = sorted(
            self._ctx.pairing.list_devices(),
            key=lambda d: (d.id != active_id, -d.last_used_at),
        )
        return [
            DeviceRow(d.id, d.name, format_last_used(d.last_used_at, now), d.id == active_id)
            for d in devices
        ]

    def revoke(self, device_id: str) -> None:
        self._ctx.pairing.revoke(device_id)

    def revoke_all(self) -> None:
        self._ctx.pairing.revoke_all()

    def status_text(self) -> str:
        active = self._ctx.sessions.active()
        if active is None:
            return "PcX Control: aguardando celular"
        return f"PcX Control: conectado a {active.device_name}"
