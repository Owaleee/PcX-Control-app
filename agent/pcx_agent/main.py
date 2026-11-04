"""Linha de comando do agente.

Modos: bandeja (padrao no Windows), --console (terminal), --demo (sensores simulados,
qualquer sistema) e --self-test SAIDA (autoteste para a CI).
"""

import argparse
import getpass
import logging
import sys
import tempfile
import threading
from pathlib import Path

from pcx_agent import __version__
from pcx_agent.api.app import build_context
from pcx_agent.config import DEFAULT_PORT, default_data_dir, load_settings
from pcx_agent.controller import NO_NETWORK_WARNING
from pcx_agent.crashlog import install_crash_logging, log_startup
from pcx_agent.logs import setup_logging
from pcx_agent.network import lan_address
from pcx_agent.pairing_uri import pairing_uri, print_pairing
from pcx_agent.server import AgentServer, PortInUseError, StartupError

DEMO_PASSWORD = "demo-password"
logger = logging.getLogger("pcx_agent.main")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcx_agent", description="Agente do PcX Control.")
    parser.add_argument("--demo", action="store_true", help="usa sensores simulados (qualquer SO)")
    parser.add_argument("--console", action="store_true", help="roda no terminal, sem bandeja")
    parser.add_argument("--data-dir", type=Path, help="pasta de dados do agente")
    parser.add_argument("--port", type=int, default=None, help=f"porta (padrao {DEFAULT_PORT})")
    parser.add_argument("--host", default="0.0.0.0", help="endereco de escuta")
    parser.add_argument("--dry-run", action="store_true", help="monta tudo e sai sem iniciar")
    parser.add_argument("--self-test", type=Path, metavar="SAIDA", help="autoteste (CI)")
    return parser


def _ask_new_password(passwords) -> None:
    print("Primeira execução: crie a senha do PC (mínimo de 8 caracteres).")
    while not passwords.is_set():
        try:
            passwords.set_password(getpass.getpass("Senha: "))
        except ValueError as exc:
            print(exc)


def _wait_until_interrupted() -> None:
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


def _provider(demo: bool):
    if demo:
        from pcx_agent.sensors.fake import FakeSensorProvider

        return FakeSensorProvider()
    from pcx_agent.sensors.windows.provider import WindowsSensorProvider

    return WindowsSensorProvider()


def run_console(args) -> int:
    data_dir = args.data_dir
    if data_dir is None and args.demo:
        data_dir = Path(tempfile.mkdtemp(prefix="pcx-demo-"))
    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    setup_logging(data_dir / "logs", console=True)
    install_crash_logging(data_dir / "logs")
    log_startup()
    settings = load_settings(data_dir=data_dir, port=args.port)
    ctx = build_context(settings, _provider(args.demo))
    try:
        if not ctx.passwords.is_set():
            if args.demo:
                ctx.passwords.set_password(DEMO_PASSWORD)
            elif not args.dry_run:
                _ask_new_password(ctx.passwords)
        print(f"PcX Control {__version__} | porta {settings.port} | dados em {settings.data_dir}")
        if args.demo:
            print(f"Modo demo (sensores simulados). Senha: {DEMO_PASSWORD}")
        qr_host = lan_address()[0] if args.host in ("0.0.0.0", "::") else args.host
        if qr_host == "127.0.0.1" and args.host in ("0.0.0.0", "::"):
            print(NO_NETWORK_WARNING)
        code = ctx.pairing.new_code()
        uri = pairing_uri(ctx.db.agent_id, qr_host, settings.port or DEFAULT_PORT, code)
        print_pairing(sys.stdout, code, uri)
        if args.dry_run:
            return 0
        server = AgentServer(ctx, args.host, settings.port)
        try:
            server.start()
        except (PortInUseError, StartupError) as exc:
            print(exc, file=sys.stderr)
            return 1
        try:
            _wait_until_interrupted()
        finally:
            server.stop()
        return 0
    finally:
        ctx.db.close()


def run_tray(args) -> int:
    from pcx_agent.controller import AgentController
    from pcx_agent.tray import texts
    from pcx_agent.winsys.autostart import AutoStart, WinRegistryRunStore, launch_command
    from pcx_agent.winsys.dialogs import show_message
    from pcx_agent.winsys.instance import acquire_single_instance

    data_dir = Path(args.data_dir) if args.data_dir is not None else default_data_dir()
    setup_logging(data_dir / "logs")
    install_crash_logging(data_dir / "logs")
    log_startup()
    settings = load_settings(data_dir=data_dir, port=args.port)
    lock = acquire_single_instance(settings.data_dir)
    if lock is None:
        show_message(texts.APP_NAME, texts.ALREADY_RUNNING)
        return 0
    ctx = None
    server = None
    try:
        ctx = build_context(settings, _provider(demo=False))
        server = AgentServer(ctx, args.host, settings.port)
        try:
            server.start()
        except PortInUseError:
            # Segue para a bandeja sem servidor: o alerta do diagnostico avisa e oferece trocar a porta.
            logger.warning("Porta %s em uso; seguindo sem servidor", settings.port)
        from pcx_agent.tray.app import TrayApp

        controller = AgentController(ctx, settings.port)
        autostart = AutoStart(WinRegistryRunStore(), launch_command())
        return TrayApp(settings, server, controller, autostart).run()
    except Exception:
        logger.exception("Falha ao iniciar o agente")
        show_message(texts.APP_NAME, texts.STARTUP_ERROR.format(pasta=settings.log_dir), error=True)
        return 1
    finally:
        if server is not None:
            server.stop()
        if ctx is not None:
            ctx.db.close()
        lock.release()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test is not None:
        from pcx_agent.selftest import run_self_test

        return run_self_test(args.self_test, demo=args.demo)
    if not args.demo and sys.platform != "win32":
        print("O agente real só roda no Windows. Use --demo para sensores simulados.", file=sys.stderr)
        return 2
    if args.demo or args.console or args.dry_run:
        return run_console(args)
    return run_tray(args)
