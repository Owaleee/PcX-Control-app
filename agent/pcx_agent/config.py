"""Configuracao do agente: pasta de dados e config.json."""

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pcx_agent import __version__

DEFAULT_PORT = 8765
CONFIG_FILE = "config.json"

logger = logging.getLogger("pcx_agent.config")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    port: int = DEFAULT_PORT
    version: str = __version__

    @property
    def config_path(self) -> Path:
        return self.data_dir / CONFIG_FILE

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "PcXControl"
    return Path.home() / ".local" / "share" / "pcx-control"


def _valid_port(value: object) -> bool:
    return type(value) is int and 1 <= value <= 65535


def _port_from_file(path: Path) -> int:
    """Le a porta do config.json. Arquivo ruim: usa o padrao e nunca reescreve o arquivo."""
    if not path.exists():
        path.write_text(json.dumps({"port": DEFAULT_PORT}, indent=2) + "\n", encoding="utf-8")
        return DEFAULT_PORT
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("config.json ilegível (%s); usando a porta %d.", exc, DEFAULT_PORT)
        return DEFAULT_PORT
    port = data.get("port", DEFAULT_PORT) if isinstance(data, dict) else None
    if not _valid_port(port):
        logger.warning(
            "Porta inválida no config.json (%r); usando a porta %d.", port, DEFAULT_PORT
        )
        return DEFAULT_PORT
    return port


def load_settings(data_dir: Path | None = None, port: int | None = None) -> Settings:
    folder = Path(data_dir) if data_dir is not None else default_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    file_port = _port_from_file(folder / CONFIG_FILE)
    return Settings(data_dir=folder, port=port if port is not None else file_port)
