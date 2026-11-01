"""Servidor do agente numa thread: a bandeja e o terminal sobem e param o Uvicorn por aqui."""

import socket
import sys
import threading
import time

import uvicorn

from pcx_agent.api.app import AppContext, create_app

# Limites do servidor: o celular so manda mensagens pequenas (auth).
WS_MAX_SIZE = 16_384
LIMIT_CONCURRENCY = 64
TIMEOUT_KEEP_ALIVE = 5
# Ping do protocolo WebSocket: fecha conexoes mortas (celular sem sinal, Wi-Fi caiu).
WS_PING_INTERVAL = 5.0
WS_PING_TIMEOUT = 10.0


class PortInUseError(Exception):
    def __init__(self, port: int) -> None:
        super().__init__(f"A porta {port} já está em uso por outro programa.")
        self.port = port


class StartupError(Exception):
    pass


def uvicorn_config(app, host: str, port: int) -> uvicorn.Config:
    return uvicorn.Config(
        app,
        host=host,
        port=port,
        access_log=False,
        log_config=None,
        ws_ping_interval=WS_PING_INTERVAL,
        ws_ping_timeout=WS_PING_TIMEOUT,
        ws_max_size=WS_MAX_SIZE,
        limit_concurrency=LIMIT_CONCURRENCY,
        timeout_keep_alive=TIMEOUT_KEEP_ALIVE,
    )


def _ensure_port_free(host: str, port: int) -> None:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        if sys.platform == "win32":
            # No Windows, SO_REUSEADDR deixaria "dividir" a porta com outro programa.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # Fora do Windows, ignora conexoes antigas em TIME_WAIT, como o Uvicorn faz.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            raise PortInUseError(port) from None


class AgentServer:
    def __init__(self, ctx: AppContext, host: str, port: int) -> None:
        self._ctx = ctx
        self._host = host
        self._port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self, timeout: float = 10.0) -> None:
        if self._port != 0:
            _ensure_port_free(self._host, self._port)
        server = uvicorn.Server(uvicorn_config(create_app(self._ctx), self._host, self._port))
        thread = threading.Thread(target=server.run, name="pcx-server", daemon=True)
        self._server, self._thread = server, thread
        thread.start()
        deadline = time.monotonic() + timeout
        while not server.started:
            if not thread.is_alive():
                raise StartupError("O servidor parou durante a inicialização.")
            if time.monotonic() > deadline:
                server.should_exit = True
                raise StartupError("O servidor não iniciou a tempo.")
            time.sleep(0.02)

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.servers:
            return self._port
        return self._server.servers[0].sockets[0].getsockname()[1]

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self, timeout: float = 5.0) -> None:
        if self._server is None or self._thread is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():  # conexoes presas: corta sem esperar
            self._server.force_exit = True
            self._thread.join(timeout=1.0)
