"""WebSocket /v1/stream: transmite as leituras para o unico celular com sessao ativa."""

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable

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


MAX_REASON_BYTES = 123  # limite do protocolo WebSocket para o motivo do fechamento


def truncate_reason(text: str, limit: int = MAX_REASON_BYTES) -> str:
    """Corta o texto em `limit` bytes UTF-8 sem partir um caractere ao meio."""
    return text.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def build_hello(
    agent_id: str, name: str, version: str, capabilities: set[str], protocol: int = PROTOCOL
) -> dict:
    return {
        "type": "hello",
        "protocol": protocol,
        "agent": {"id": agent_id, "name": name, "version": version},
        "capabilities": sorted(capabilities),
    }


def build_snapshot_message(seq: int, snapshot: Snapshot) -> dict:
    return {
        "type": "snapshot",
        "seq": seq,
        "t": snapshot.t.isoformat(),
        "data": snapshot.model_dump(mode="json"),
    }


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
        await ws.close(code=code, reason=truncate_reason(reason))


def register_stream(app: FastAPI, ctx, hub: StreamHub, auth_timeout_s: float) -> None:
    @app.websocket("/v1/stream")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        try:
            first = await asyncio.wait_for(ws.receive(), timeout=auth_timeout_s)
        except TimeoutError:
            logger.info(
                "Celular não se autenticou a tempo ip=%s", ws.client.host if ws.client else "?"
            )
            await _close(ws, CLOSE_AUTH_TIMEOUT, "Autenticação não enviada")
            return
        if first["type"] == "websocket.disconnect":
            return
        parsed = _parse_auth(first)
        device = await asyncio.to_thread(ctx.pairing.authenticate, parsed[0]) if parsed else None
        ip = ws.client.host if ws.client else "desconhecido"
        if parsed is None or device is None:
            logger.info("Celular com token inválido ip=%s (precisa parear de novo)", ip)
            await _close(ws, CLOSE_INVALID_TOKEN, "Token inválido")
            return
        await _serve(ws, ctx, hub, device, takeover=parsed[1], ip=ip)


async def _serve(
    ws: WebSocket, ctx, hub: StreamHub, device: Device, takeover: bool, ip: str = "desconhecido"
) -> None:
    loop = asyncio.get_running_loop()
    evicted = asyncio.Event()
    revoked = asyncio.Event()

    def notify(event: asyncio.Event) -> Callable[[], None]:
        # Pode ser chamado de outra thread (bandeja, rotas HTTP): entrega no laco certo.
        def call() -> None:
            with contextlib.suppress(RuntimeError):  # laco ja encerrado
                loop.call_soon_threadsafe(event.set)

        return call

    session = ActiveSession(
        device.id, device.name, evict=notify(evicted), on_revoke=notify(revoked)
    )
    slot = _Slot()
    previous = ctx.sessions.active()
    result = ctx.sessions.acquire(session, takeover)
    if result.status == "busy":
        logger.info(
            "Celular recusado: PC ocupado por %r ip=%s aparelho=%r",
            result.active_device_name, ip, device.name,
        )
        await _close(ws, CLOSE_BUSY, result.active_device_name or "")
        return
    if previous is not None and previous.device_id != device.id:
        logger.info("Celular assumiu a sessão de %r ip=%s aparelho=%r", previous.device_name, ip,
                    device.name)
    logger.info("Celular conectado ip=%s aparelho=%r", ip, device.name)
    reason = "conexão encerrada"

    hub.slot = slot
    recv_task = asyncio.create_task(_drain(ws, ctx, device.id))
    evict_task = asyncio.create_task(evicted.wait())
    revoke_task = asyncio.create_task(revoked.wait())
    try:
        agent_id, agent_name = await asyncio.to_thread(lambda: (ctx.db.agent_id, ctx.db.agent_name))
        await ws.send_json(
            build_hello(
                agent_id, agent_name, ctx.settings.version, ctx.provider.capabilities(), ctx.settings.protocol
            )
        )
        ctx.sessions.touch(device.id)
        ctx.sampler.nudge()
        while True:
            get_task = asyncio.create_task(slot.get())
            done, _ = await asyncio.wait(
                {get_task, recv_task, evict_task, revoke_task},
                timeout=1.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if get_task in done:
                seq, snapshot = get_task.result()
                await ws.send_json(build_snapshot_message(seq, snapshot))
                ctx.sessions.touch(device.id)  # enviar com sucesso prova que o celular esta la
                continue
            get_task.cancel()
            if revoke_task in done:
                reason = "desconectado no PC"
                await _close(ws, CLOSE_INVALID_TOKEN, "Aparelho desconectado no PC")
                break
            if evict_task in done:
                reason = "sessão assumida por outro aparelho"
                await _close(ws, CLOSE_TAKEN_OVER, "Sessão assumida por outro aparelho")
                break
            if recv_task in done:
                reason = "o celular fechou a conexão"
                break
            if ctx.sessions.active() is not session:
                reason = "sessão expirou"
                await _close(ws, CLOSE_GOING_AWAY, "Sessão encerrada")
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        logger.exception("Falha na transmissao")
    finally:
        recv_task.cancel()
        evict_task.cancel()
        revoke_task.cancel()
        if hub.slot is slot:
            hub.slot = None
        ctx.sessions.release(device.id, session=session)
        logger.info("Celular desconectado ip=%s aparelho=%r motivo=%s", ip, device.name, reason)
