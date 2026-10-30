"""WebSocket /v1/stream: transmite as leituras para o unico celular com sessao ativa."""

import asyncio
import contextlib
import json
import logging

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from pcx_agent import PROTOCOL
from pcx_agent.auth.pairing import Device
from pcx_agent.sensors.base import Snapshot
from pcx_agent.session import ActiveSession

logger = logging.getLogger("pcx_agent.stream")

MAX_AUTH_BYTES = 4096
CLOSE_INVALID_TOKEN = 4401
CLOSE_AUTH_TIMEOUT = 4408
CLOSE_TAKEN_OVER = 4409
CLOSE_BUSY = 4423
CLOSE_GOING_AWAY = 1001


class _Slot:
    """Fila de 1 item: a leitura mais nova substitui a anterior."""

    def __init__(self) -> None:
        self._item: tuple[int, Snapshot] | None = None
        self._event = asyncio.Event()

    def put(self, seq: int, snapshot: Snapshot) -> None:
        self._item = (seq, snapshot)
        self._event.set()

    async def get(self) -> tuple[int, Snapshot]:
        await self._event.wait()
        self._event.clear()
        assert self._item is not None
        return self._item


class StreamHub:
    """Liga o Sampler a conexao ativa. Ha no maximo uma conexao recebendo."""

    def __init__(self) -> None:
        self.slot: _Slot | None = None
        self.seq = 0

    def publish(self, snapshot: Snapshot) -> None:
        self.seq += 1
        if self.slot is not None:
            self.slot.put(self.seq, snapshot)


def _parse_auth(message: dict) -> tuple[str, bool] | None:
    text = message.get("text")
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_AUTH_BYTES:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("type") != "auth":
        return None
    token = data.get("token")
    if not isinstance(token, str) or not token:
        return None
    return token, data.get("takeover") is True


async def _drain(ws: WebSocket, ctx, device_id: str) -> None:
    """Le o que o celular manda (pings) e mantem a sessao viva."""
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            return
        ctx.sessions.touch(device_id)


async def _close(ws: WebSocket, code: int, reason: str = "") -> None:
    with contextlib.suppress(Exception):  # o cliente pode ja ter ido embora
        await ws.close(code=code, reason=reason)


def register_stream(app: FastAPI, ctx, hub: StreamHub, auth_timeout_s: float) -> None:
    @app.websocket("/v1/stream")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        try:
            first = await asyncio.wait_for(ws.receive(), timeout=auth_timeout_s)
        except TimeoutError:
            await _close(ws, CLOSE_AUTH_TIMEOUT, "Autenticação não enviada")
            return
        if first["type"] == "websocket.disconnect":
            return
        parsed = _parse_auth(first)
        device = ctx.pairing.authenticate(parsed[0]) if parsed else None
        if parsed is None or device is None:
            await _close(ws, CLOSE_INVALID_TOKEN, "Token inválido")
            return
        await _serve(ws, ctx, hub, device, takeover=parsed[1])


async def _serve(ws: WebSocket, ctx, hub: StreamHub, device: Device, takeover: bool) -> None:
    evicted = asyncio.Event()
    session = ActiveSession(device.id, device.name, evict=evicted.set)
    slot = _Slot()
    result = ctx.sessions.acquire(session, takeover)
    if result.status == "busy":
        await _close(ws, CLOSE_BUSY, result.active_device_name or "")
        return

    hub.slot = slot
    recv_task = asyncio.create_task(_drain(ws, ctx, device.id))
    evict_task = asyncio.create_task(evicted.wait())
    try:
        await ws.send_json(
            {
                "type": "hello",
                "protocol": PROTOCOL,
                "agent": {
                    "id": ctx.db.agent_id,
                    "name": ctx.db.agent_name,
                    "version": ctx.settings.version,
                },
                "capabilities": sorted(ctx.provider.capabilities()),
            }
        )
        ctx.sampler.nudge()
        while True:
            get_task = asyncio.create_task(slot.get())
            done, _ = await asyncio.wait(
                {get_task, recv_task, evict_task},
                timeout=1.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if get_task in done:
                seq, snapshot = get_task.result()
                await ws.send_json(
                    {
                        "type": "snapshot",
                        "seq": seq,
                        "t": snapshot.t.isoformat(),
                        "data": snapshot.model_dump(mode="json"),
                    }
                )
                continue
            get_task.cancel()
            if evict_task in done:
                await _close(ws, CLOSE_TAKEN_OVER, "Sessão assumida por outro aparelho")
                break
            if recv_task in done:
                break
            if ctx.sessions.active() is not session:
                await _close(ws, CLOSE_GOING_AWAY, "Sessão encerrada")
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        logger.exception("Falha na transmissao")
    finally:
        recv_task.cancel()
        evict_task.cancel()
        if hub.slot is slot:
            hub.slot = None
        ctx.sessions.release(device.id, session=session)
