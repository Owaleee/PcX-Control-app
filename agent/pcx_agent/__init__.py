"""Agente do PcX Control."""

__version__ = "0.2.0"
PROTOCOL = 1


def assets_path(name: str):
    """Caminho de um arquivo em pcx_agent/assets (instalado ou dentro do PyInstaller)."""
    from importlib.resources import files
    from pathlib import Path

    return Path(str(files("pcx_agent") / "assets" / name))
