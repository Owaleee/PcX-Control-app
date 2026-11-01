"""Linha de comando do agente: python -m pcx_agent [--demo]."""

import argparse
import getpass
import sys
import tempfile
from pathlib import Path

from pcx_agent import __version__
from pcx_agent.api.app import build_context, create_app
from pcx_agent.config import DEFAULT_PORT, load_settings
from pcx_agent.pairing_uri import local_ipv4, pairing_uri, print_pairing

DEMO_PASSWORD = "demo-password"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcx_agent", description="Agente do PcX Control.")
    parser.add_argument("--demo", action="store_true", help="usa sensores simulados (qualquer SO)")
    parser.add_argument("--data-dir", type=Path, help="pasta de dados do agente")
    parser.add_argument("--port", type=int, default=None, help=f"porta (padrao {DEFAULT_PORT})")
    parser.add_argument("--host", default="0.0.0.0", help="endereco de escuta")
    parser.add_argument("--dry-run", action="store_true", help="monta tudo e sai sem iniciar")
    return parser


def _ask_new_password(passwords) -> None:
    print("Primeira execução: crie a senha do PC (mínimo de 8 caracteres).")
    while not passwords.is_set():
        try:
            passwords.set_password(getpass.getpass("Senha: "))
        except ValueError as exc:
            print(exc)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.demo and sys.platform != "win32":
        print("O agente real só roda no Windows. Use --demo para sensores simulados.", file=sys.stderr)
        return 2

    data_dir = args.data_dir
    if data_dir is None and args.demo:
        data_dir = Path(tempfile.mkdtemp(prefix="pcx-demo-"))
    settings = load_settings(data_dir=data_dir, port=args.port)

    if args.demo:
        from pcx_agent.sensors.fake import FakeSensorProvider

        provider = FakeSensorProvider()
    else:
        from pcx_agent.sensors.windows.provider import WindowsSensorProvider

        provider = WindowsSensorProvider()

    ctx = build_context(settings, provider)
    try:
        if not ctx.passwords.is_set():
            if args.demo:
                ctx.passwords.set_password(DEMO_PASSWORD)
            elif not args.dry_run:
                _ask_new_password(ctx.passwords)
        print(f"PcX Control {__version__} | porta {settings.port} | dados em {settings.data_dir}")
        if args.demo:
            print(f"Modo demo (sensores simulados). Senha: {DEMO_PASSWORD}")
        qr_host = local_ipv4() if args.host in ("0.0.0.0", "::") else args.host
        code = ctx.pairing.new_code()
        uri = pairing_uri(ctx.db.agent_id, qr_host, settings.port or DEFAULT_PORT, code)
        print_pairing(sys.stdout, code, uri)
        if args.dry_run:
            return 0

        import uvicorn

        uvicorn.run(
            create_app(ctx),
            host=args.host,
            port=settings.port,
            access_log=False,
            log_level="info",
            # Ping do protocolo WebSocket: fecha conexoes mortas (celular sem sinal, Wi-Fi caiu).
            ws_ping_interval=5.0,
            ws_ping_timeout=10.0,
        )
        return 0
    finally:
        ctx.db.close()
