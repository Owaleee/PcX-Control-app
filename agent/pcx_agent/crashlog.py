"""Registro de travamentos: nenhum erro some sem deixar rastro na pasta `logs`.

- Excecao nao tratada em qualquer thread (principal, servidor, bandeja, coletor): `agent.log`
  com nivel CRITICAL, o nome da thread e o traceback.
- Erro no laco do servidor (asyncio): `agent.log` com nivel ERROR.
- Trava nativa (uma DLL de driver derruba o processo): `crash.log`, com a pilha de cada thread,
  escrita pelo `faulthandler` no momento da trava. Ele so grava nomes de funcoes e linhas de
  codigo, nunca valores: senha, codigo e token nao aparecem ali.
"""

import contextlib
import faulthandler
import logging
import platform
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pcx_agent import __version__

CRASH_FILE = "crash.log"
MAX_CRASH_BYTES = 1_048_576
logger = logging.getLogger("pcx_agent.crash")

_state: dict[str, object] = {}


def trim_crash_file(path: Path, max_bytes: int = MAX_CRASH_BYTES) -> None:
    """Mantem so o final do arquivo, cortando numa quebra de linha."""
    if not path.exists() or path.stat().st_size <= max_bytes:
        return
    data = path.read_bytes()[-max_bytes:]
    newline = data.find(b"\n")
    if 0 <= newline < len(data) - 1:
        data = data[newline + 1 :]
    path.write_bytes(data)


def _thread_name() -> str:
    return threading.current_thread().name


def _excepthook(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical(
        "Erro nao tratado na thread %s", _thread_name(), exc_info=(exc_type, exc_value, exc_traceback)
    )


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    if issubclass(args.exc_type, SystemExit):
        return
    name = args.thread.name if args.thread is not None else "desconhecida"
    logger.critical(
        "Erro nao tratado na thread %s",
        name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def asyncio_exception_handler(_loop, context: dict) -> None:
    """Para `loop.set_exception_handler`: erro no laco do servidor vai para o log."""
    exc = context.get("exception")
    exc_info = (type(exc), exc, exc.__traceback__) if isinstance(exc, BaseException) else None
    logger.error("Erro no laco do servidor: %s", context.get("message", "sem mensagem"), exc_info=exc_info)


def _open_crash_file(log_dir: Path) -> TextIO:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / CRASH_FILE
    trim_crash_file(path)
    handle = path.open("a", encoding="utf-8")
    started = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    handle.write(f"=== PcX Control {__version__} iniciado em {started} ===\n")
    handle.flush()
    return handle


def install_crash_logging(log_dir: Path) -> None:
    """Instala os ganchos. Chamar logo depois de `setup_logging`."""
    if _state:
        uninstall_crash_logging()
    handle = _open_crash_file(Path(log_dir))
    _state.update(
        excepthook=sys.excepthook,
        thread_excepthook=threading.excepthook,
        faulthandler_was_enabled=faulthandler.is_enabled(),
        handle=handle,
    )
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    faulthandler.enable(file=handle, all_threads=True)


def uninstall_crash_logging() -> None:
    """Desfaz `install_crash_logging` (usado nos testes)."""
    if not _state:
        return
    faulthandler.disable()
    sys.excepthook = _state["excepthook"]
    threading.excepthook = _state["thread_excepthook"]
    handle = _state["handle"]
    handle.close()
    if _state["faulthandler_was_enabled"]:
        # Volta para a saida de erro original; num terminal capturado (testes) ela pode nao ter
        # descritor de arquivo, e ai o faulthandler simplesmente fica desligado.
        with contextlib.suppress(AttributeError, OSError, ValueError):
            faulthandler.enable(file=sys.__stderr__)
    _state.clear()


def log_startup() -> None:
    """Uma linha com o que ajuda a reproduzir um problema: versoes e se e o .exe."""
    frozen = "sim" if getattr(sys, "frozen", False) else "nao"
    logger.info(
        "PcX Control %s | sistema %s %s (%s) | Python %s | executavel: %s",
        __version__,
        platform.system(),
        platform.release(),
        platform.version(),
        platform.python_version(),
        frozen,
    )
