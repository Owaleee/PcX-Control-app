"""API HTTP /v1 do agente."""

import asyncio
import logging
import math
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from pcx_agent import PROTOCOL
from pcx_agent.api.stream import StreamHub, register_stream
from pcx_agent.auth.pairing import Device, PairError, PairingService
from pcx_agent.auth.passwords import PasswordService
from pcx_agent.auth.ratelimit import RateLimiter
from pcx_agent.config import Settings
from pcx_agent.sampler import Sampler
from pcx_agent.sensors.base import METRIC_NAMES, SensorProvider
from pcx_agent.session import SessionManager
from pcx_agent.storage.db import Database
from pcx_agent.storage.history import VALID_RANGES, HistoryStore


@dataclass
class AppContext:
    settings: Settings
    db: Database
    passwords: PasswordService
    limiter: RateLimiter
    pairing: PairingService
    sessions: SessionManager
    history: HistoryStore
    sampler: Sampler
    provider: SensorProvider


def build_context(
    settings: Settings,
    provider: SensorProvider,
    *,
    session_timeout_s: float = 15.0,
    **sampler_options: float,
) -> AppContext:
    db = Database(settings.data_dir / "pcx.db")
    passwords = PasswordService(db)
    limiter = RateLimiter()
    sessions = SessionManager(timeout_s=session_timeout_s)
    history = HistoryStore(db)
    pairing = PairingService(db, passwords, limiter)
    pairing.on_revoke = sessions.revoke  # revogar um aparelho derruba a transmissao dele
    return AppContext(
        settings=settings,
        db=db,
        passwords=passwords,
        limiter=limiter,
        pairing=pairing,
        sessions=sessions,
        history=history,
        sampler=Sampler(provider, history, sessions.has_active, **sampler_options),
        provider=provider,
    )


pairing_log = logging.getLogger("pcx_agent.pairing")
_RESULTS = {
    "rate_limited": "bloqueado",
    "bad_credentials": "senha_errada",
    "code_invalid_or_expired": "codigo_invalido",
    "invalid_name": "nome_invalido",
}


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
        **extra: object,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers
        self.extra = extra


class PairRequest(BaseModel):
    device_name: str
    code: str | None = None
    password: str | None = None


def _pair_error(err: PairError) -> ApiError:
    if err.kind == "rate_limited":
        wait = err.retry_after or 60.0
        return ApiError(
            429,
            "rate_limited",
            f"Muitas tentativas. Tente de novo em {math.ceil(wait)} s.",
            headers={"Retry-After": str(math.ceil(wait))},
            retry_after=wait,
        )
    if err.kind == "bad_credentials":
        left = err.attempts_left
        text = "Senha incorreta." + (f" Restam {left} tentativas." if left is not None else "")
        return ApiError(401, "bad_credentials", text, attempts_left=left)
    if err.kind == "code_invalid_or_expired":
        return ApiError(410, "code_invalid_or_expired", "Código expirado. Gere outro no PC.")
    return ApiError(422, "invalid_name", "Nome do aparelho inválido: use de 1 a 64 caracteres.")


def _token_from(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def create_app(
    ctx: AppContext, *, run_sampler: bool = True, auth_timeout_s: float = 5.0
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = asyncio.create_task(ctx.sampler.run()) if run_sampler else None
        yield
        if task is not None:
            ctx.sampler.stop()
            await task
            ctx.provider.close()

    app = FastAPI(
        title="PcX Control",
        version=ctx.settings.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    hub = StreamHub()
    ctx.sampler.on_snapshot = hub.publish
    register_stream(app, ctx, hub, auth_timeout_s)

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, err: ApiError) -> JSONResponse:
        body = {"code": err.code, "message": err.message, **err.extra}
        return JSONResponse(body, status_code=err.status, headers=err.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, err: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) or "corpo" for e in err.errors()})
        body = {"code": "invalid_request", "message": f"Campos inválidos: {', '.join(fields)}."}
        return JSONResponse(body, status_code=422)

    def authenticated_device(request: Request) -> Device:
        token = _token_from(request)
        device = ctx.pairing.authenticate(token) if token else None
        if device is None:
            raise ApiError(401, "invalid_token", "Este celular não está pareado. Pareie de novo.")
        return device

    def active_device(device: Device = Depends(authenticated_device)) -> Device:
        current = ctx.sessions.active()
        if current is not None and current.device_id != device.id:
            raise ApiError(
                409,
                "session_busy",
                f"PC em uso por {current.device_name}.",
                active_device=current.device_name,
            )
        return device

    agent_info = {
        "id": ctx.db.agent_id,
        "name": ctx.db.agent_name,
        "version": ctx.settings.version,
        "protocol": PROTOCOL,
    }

    @app.get("/v1/info")
    def info() -> dict:
        return {
            "agent_id": agent_info["id"],
            "name": ctx.db.agent_name,
            "version": agent_info["version"],
            "protocol": PROTOCOL,
            "busy": ctx.sessions.has_active(),
        }

    @app.post("/v1/pair")
    def pair(body: PairRequest, request: Request) -> dict:
        client_ip = request.client.host if request.client else "desconhecido"
        method = "qr" if body.code is not None else "senha"
        try:
            result = ctx.pairing.pair(
                body.device_name, code=body.code, password=body.password, client_ip=client_ip
            )
        except PairError as err:
            pairing_log.info(
                "Pareamento ip=%s metodo=%s resultado=%s aparelho=%r",
                client_ip, method, _RESULTS[err.kind], body.device_name,
            )
            raise _pair_error(err) from None
        pairing_log.info(
            "Pareamento ip=%s metodo=%s resultado=pareado aparelho=%r",
            client_ip, method, body.device_name,
        )
        return {
            "device_id": result.device_id,
            "token": result.token,
            "agent": {**agent_info, "name": ctx.db.agent_name},
        }

    @app.get("/v1/snapshot")
    def snapshot(_device: Device = Depends(active_device)) -> dict:
        latest = ctx.sampler.latest
        if latest is None:
            raise ApiError(503, "starting", "O agente está iniciando. Tente em alguns segundos.")
        return latest.model_dump(mode="json")

    @app.get("/v1/history")
    def history(metric: str, range: str, _device: Device = Depends(active_device)) -> dict:
        if metric not in METRIC_NAMES:
            raise ApiError(422, "invalid_metric", f"Métrica desconhecida: {metric}.")
        if range not in VALID_RANGES:
            raise ApiError(422, "invalid_range", "Intervalo inválido. Use 15m, 1h ou 24h.")
        points = ctx.history.query(metric, range, time.time())
        return {
            "metric": metric,
            "range": range,
            "points": [{"t": p.t, "avg": p.avg, "max": p.max} for p in points],
        }

    @app.delete("/v1/devices/me", status_code=204)
    def forget_me(device: Device = Depends(authenticated_device)) -> Response:
        ctx.pairing.revoke(device.id)
        ctx.sessions.release(device.id)
        return Response(status_code=204)

    return app
