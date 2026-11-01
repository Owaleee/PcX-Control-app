"""Configuracao do agente e pasta de dados."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pcx_agent import __version__

DEFAULT_PORT = 8765


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    port: int = DEFAULT_PORT
    version: str = __version__


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "PcXControl"
    return Path.home() / ".local" / "share" / "pcx-control"


def load_settings(data_dir: Path | None = None, port: int | None = None) -> Settings:
    folder = Path(data_dir) if data_dir is not None else default_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return Settings(data_dir=folder, port=port if port is not None else DEFAULT_PORT)
