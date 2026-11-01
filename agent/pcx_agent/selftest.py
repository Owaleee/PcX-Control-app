"""Autoteste: sobe o servidor numa porta livre, consulta /v1/info e le os sensores.

Usado pela CI no .exe congelado para provar que nenhum modulo ficou de fora.
"""

import json
import tempfile
import urllib.request
from pathlib import Path

from pcx_agent import __version__
from pcx_agent.api.app import build_context
from pcx_agent.config import load_settings
from pcx_agent.server import AgentServer


def _provider(demo: bool):
    if demo:
        from pcx_agent.sensors.fake import FakeSensorProvider

        return FakeSensorProvider()
    from pcx_agent.sensors.windows.provider import WindowsSensorProvider

    return WindowsSensorProvider()


def run_self_test(out: Path, *, demo: bool) -> int:
    out = Path(out)
    try:
        with tempfile.TemporaryDirectory(prefix="pcx-selftest-") as folder:
            provider = _provider(demo)
            ctx = build_context(load_settings(data_dir=Path(folder)), provider)
            server = AgentServer(ctx, "127.0.0.1", 0)
            try:
                server.start()
                url = f"http://127.0.0.1:{server.bound_port}/v1/info"
                with urllib.request.urlopen(url, timeout=10) as response:
                    info = json.loads(response.read())
                provider.read()
                result = {
                    "ok": info.get("version") == __version__,
                    "version": __version__,
                    "capabilities": sorted(provider.capabilities()),
                    "port": server.bound_port,
                }
            finally:
                server.stop()
                ctx.db.close()
                provider.close()
    except Exception as exc:  # noqa: BLE001 - o autoteste relata qualquer falha
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0 if result["ok"] else 1
