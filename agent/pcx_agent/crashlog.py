"""Registro de travamentos: nenhum erro some sem deixar rastro na pasta `logs`.

- Excecao nao tratada em qualquer thread (principal, servidor, bandeja, coletor): `agent.log`
  com nivel CRITICAL, o nome da thread e o traceback.
- Erro no laco do servidor (asyncio): `agent.log` com nivel ERROR.
- Trava nativa (uma DLL de driver derruba o processo): `crash.log`, com a pilha de cada thread,
  escrita pelo `faulthandler` no momento da trava. Ele so grava nomes de funcoes e linhas de
  codigo, nunca valores: senha, codigo e token nao aparecem ali.

No Windows o `faulthandler` tambem registra excecoes que um driver ou o ctypes tratam sozinhos
("Windows fatal exception" com o processo seguindo vivo). Por isso cada execucao termina com a
linha ENDED_NORMALLY: pilha seguida dessa linha nao foi uma queda.
"""

import atexit
import contextlib
import faulthandler
import json
import logging
import platform
import re
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pcx_agent import __version__
from pcx_agent.logs import LOG_FILE, redact

CRASH_FILE = "crash.log"
ENDED_NORMALLY = "=== encerrado normalmente ==="
MAX_CRASH_BYTES = 1_048_576
CRASH_PREFIX = "crash-"
MAX_CRASH_FILES = 10
_HEADER_RE = re.compile(r"^=== PcX Control .* iniciado em .* ===\s*$")
_CRASH_NAME_RE = re.compile(r"^crash-(\d{8}-\d{6})(?:-(\d+))?\.log$")
_LOG_TAIL_BYTES = 65_536
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


def _crash_order(path: Path) -> tuple[str, int]:
    match = _CRASH_NAME_RE.match(path.name)
    return (match.group(1), int(match.group(2) or 1)) if match else ("", 0)


def write_exception_file(log_dir: Path, thread_name: str, text: str, now: datetime) -> Path:
    """Grava um arquivo `crash-AAAAMMDD-HHMMSS.log` por excecao e guarda so os 10 mais recentes."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    base = f"{CRASH_PREFIX}{now:%Y%m%d-%H%M%S}"
    path = log_dir / f"{base}.log"
    number = 1
    while path.exists():
        number += 1
        path = log_dir / f"{base}-{number}.log"
    stamp = now.isoformat(timespec="seconds")
    path.write_text(redact(f"Thread: {thread_name}\nQuando: {stamp}\n\n{text}"), encoding="utf-8")
    existing = sorted(
        (p for p in log_dir.glob(f"{CRASH_PREFIX}*.log") if _CRASH_NAME_RE.match(p.name)), key=_crash_order
    )
    for old in existing[:-MAX_CRASH_FILES]:
        with contextlib.suppress(OSError):
            old.unlink()
    return path


def _save_exception_file(thread_name: str, exc_info) -> None:
    log_dir = _state.get("log_dir")
    if log_dir is None:
        return
    try:
        text = "".join(traceback.format_exception(*exc_info))
        write_exception_file(log_dir, thread_name, text, datetime.now(UTC))
    except Exception:  # o registro do travamento nunca pode causar outro erro
        logger.warning("Nao foi possivel gravar o arquivo do travamento", exc_info=True)


def _thread_name() -> str:
    return threading.current_thread().name


def _excepthook(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    exc_info = (exc_type, exc_value, exc_traceback)
    logger.critical("Erro nao tratado na thread %s", _thread_name(), exc_info=exc_info)
    _save_exception_file(_thread_name(), exc_info)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    if issubclass(args.exc_type, SystemExit):
        return
    name = args.thread.name if args.thread is not None else "desconhecida"
    exc_info = (args.exc_type, args.exc_value, args.exc_traceback)
    logger.critical("Erro nao tratado na thread %s", name, exc_info=exc_info)
    _save_exception_file(name, exc_info)


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
        log_dir=Path(log_dir),
    )
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    faulthandler.enable(file=handle, all_threads=True)
    atexit.register(mark_normal_exit)


def maintenance(log_dir: Path) -> None:
    """Corta o `crash.log` que passou de 1 MiB com o agente rodando e reabre o handle do faulthandler."""
    path = Path(log_dir) / CRASH_FILE
    if not path.exists() or path.stat().st_size <= MAX_CRASH_BYTES:
        return
    handle = _state.get("handle")
    if handle is None or handle.closed:
        trim_crash_file(path)
        return
    faulthandler.disable()
    handle.close()
    try:
        trim_crash_file(path)
    finally:
        new_handle = path.open("a", encoding="utf-8")
        _state["handle"] = new_handle
        faulthandler.enable(file=new_handle, all_threads=True)


@dataclass(frozen=True)
class PreviousSession:
    """Como a execucao anterior terminou. `last_seen` e o ultimo registro dela no agent.log."""

    crashed: bool
    last_seen: datetime | None


def _last_log_time(log_dir: Path) -> datetime | None:
    path = log_dir / LOG_FILE
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - _LOG_TAIL_BYTES))
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            return datetime.fromisoformat(json.loads(line)["ts"])
        except (ValueError, KeyError, TypeError):
            continue
    return None


def previous_session(log_dir: Path, boot_time: float) -> PreviousSession:
    """Decide se a execucao anterior caiu. Chamar antes de `install_crash_logging`.

    Cai = a ultima sessao do `crash.log` nao terminou normalmente E o ultimo registro dela no
    `agent.log` e depois do boot do Windows (num desligamento o processo pode morrer sem `atexit`).
    """
    log_dir = Path(log_dir)
    last_seen = _last_log_time(log_dir)
    try:
        lines = (log_dir / CRASH_FILE).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return PreviousSession(False, last_seen)
    starts = [i for i, line in enumerate(lines) if _HEADER_RE.match(line)]
    if not starts or last_seen is None:
        return PreviousSession(False, last_seen)
    last_session = lines[starts[-1] + 1 :]
    if any(line.strip() == ENDED_NORMALLY for line in last_session):
        return PreviousSession(False, last_seen)
    return PreviousSession(last_seen.timestamp() > boot_time, last_seen)


def mark_normal_exit() -> None:
    """Grava ENDED_NORMALLY uma vez so por execucao (atexit, ou o fim da sessao do Windows)."""
    handle = _state.get("handle")
    if handle is None or handle.closed or _state.get("marked"):
        return
    handle.write(ENDED_NORMALLY + "\n")
    handle.flush()
    _state["marked"] = True


def uninstall_crash_logging() -> None:
    """Desfaz `install_crash_logging` (usado nos testes)."""
    if not _state:
        return
    faulthandler.disable()
    atexit.unregister(mark_normal_exit)
    mark_normal_exit()
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
