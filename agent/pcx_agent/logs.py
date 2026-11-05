"""Logs do agente: JSON por linha, rotacao de 5 x 1 MiB e nada de segredos."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = "agent.log"
MAX_BYTES = 1_048_576
BACKUP_COUNT = 4  # 5 arquivos no total
GPU_LOG_FILE = "gpu.log"
GPU_MAX_BYTES = 524_288
GPU_BACKUP_COUNT = 1  # 2 arquivos de 512 KiB
SENSORS_LOGGER = "pcx_agent.sensors"
REDACTED = "[oculto]"

# Tokens e codigos vem de secrets.token_urlsafe: 22+ caracteres de base64url.
_SECRET_RE = re.compile(r"[A-Za-z0-9_-]{22,}")
# O codigo dentro da URI de pareamento, qualquer que seja o tamanho.
_URI_CODE_RE = re.compile(r"(pcx://\S*?[?&]c=)[^&\s]+")
_MARK = "_pcx_handler"


def redact(text: str) -> str:
    text = _URI_CODE_RE.sub(lambda m: m.group(1) + REDACTED, text)
    return _SECRET_RE.sub(REDACTED, text)


class RedactFilter(logging.Filter):
    """Aplica `redact` na mensagem ja formatada e na excecao."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            entry["exc"] = record.exc_text
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(log_dir: Path, *, console: bool = False, level: int = logging.INFO) -> None:
    """Configura o logger raiz. Chamar de novo troca os handlers do agente, sem duplicar."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if getattr(handler, _MARK, False):
            root.removeHandler(handler)
            handler.close()

    redactor = RedactFilter()
    file_handler = RotatingFileHandler(
        log_dir / LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())
    handlers: list[logging.Handler] = [file_handler]
    if console and sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handlers.append(stream)
    for handler in handlers:
        handler.addFilter(redactor)
        setattr(handler, _MARK, True)
        root.addHandler(handler)
    root.setLevel(level)

    # gpu.log: so os sensores; o logger continua propagando para o agent.log.
    sensors = logging.getLogger(SENSORS_LOGGER)
    for handler in sensors.handlers[:]:
        if getattr(handler, _MARK, False):
            sensors.removeHandler(handler)
            handler.close()
    gpu_handler = RotatingFileHandler(
        log_dir / GPU_LOG_FILE, maxBytes=GPU_MAX_BYTES, backupCount=GPU_BACKUP_COUNT, encoding="utf-8"
    )
    gpu_handler.setFormatter(JsonFormatter())
    gpu_handler.addFilter(redactor)
    setattr(gpu_handler, _MARK, True)
    sensors.addHandler(gpu_handler)
    # O Uvicorn pode ter configurado os proprios loggers sem propagar: tudo vai para a raiz.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(name)
        for handler in uv.handlers[:]:
            uv.removeHandler(handler)
        uv.propagate = True
        uv.disabled = False
