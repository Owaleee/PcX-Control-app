"""Autoteste: sobe o servidor numa porta livre, consulta /v1/info e le os sensores.

Usado pela CI no .exe congelado para provar que nenhum modulo ficou de fora.
"""

import json
import sys
import tempfile
import urllib.request
from pathlib import Path

from pcx_agent import __version__
from pcx_agent.api.app import build_context
from pcx_agent.config import load_settings
from pcx_agent.network import lan_address, parse_profiles, profile_output_status, run_profile_script
from pcx_agent.server import AgentServer

IS_WINDOWS = sys.platform == "win32"


def _check_tray() -> None:
    """Carrega o que a bandeja usa: o PyInstaller costuma esquecer modulos importados dinamicamente."""
    import tkinter as tk

    import pystray  # noqa: F401 - escolhe o backend do Windows ao importar

    import pcx_agent.tray.app  # noqa: F401
    from pcx_agent.tray.qr import qr_image

    qr_image("pcx://pair?v=1&id=teste&h=127.0.0.1&p=8765&c=teste")
    root = tk.Tk()
    root.withdraw()
    root.destroy()


def _provider(demo: bool):
    if demo:
        from pcx_agent.sensors.fake import FakeSensorProvider

        return FakeSensorProvider()
    from pcx_agent.sensors.windows.provider import WindowsSensorProvider

    return WindowsSensorProvider()


def _network() -> dict:
    """Prova no .exe a escolha do IP (psutil) e a leitura do tipo de rede (PowerShell)."""
    ip, interface = lan_address()
    raw = run_profile_script()
    return {
        "ip": ip,
        "interface": interface,
        "profiles": len(parse_profiles(raw)),
        "profile_output": profile_output_status(raw),
    }


def run_self_test(out: Path, *, demo: bool) -> int:
    out = Path(out)
    try:
        with tempfile.TemporaryDirectory(prefix="pcx-selftest-") as folder:
            provider = _provider(demo)
            ctx = build_context(load_settings(data_dir=Path(folder)), provider)
            server = AgentServer(ctx, "127.0.0.1", 0)
            started = False
            try:
                server.start()
                started = True
                url = f"http://127.0.0.1:{server.bound_port}/v1/info"
                with urllib.request.urlopen(url, timeout=10) as response:
                    info = json.loads(response.read())
                provider.read()
                tray = "pulado"
                if IS_WINDOWS:
                    _check_tray()
                    tray = "ok"
                result = {
                    "ok": info.get("version") == __version__,
                    "version": __version__,
                    "capabilities": sorted(provider.capabilities()),
                    "port": server.bound_port,
                    "tray": tray,
                    "network": _network(),
                }
            finally:
                server.stop()  # ao parar, o servidor ja fecha os sensores
                ctx.db.close()
                if not started:
                    provider.close()
    except Exception as exc:  # noqa: BLE001 - o autoteste relata qualquer falha
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0 if result["ok"] else 1
