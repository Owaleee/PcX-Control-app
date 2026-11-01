"""Iniciar com o Windows: valor na chave Run do usuario atual (HKCU)."""

import sys
from pathlib import PurePosixPath, PureWindowsPath
from typing import Protocol

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "PcXControl"


class RunStore(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class WinRegistryRunStore:
    """A chave Run de verdade, via winreg (so no Windows)."""

    def get(self, name: str) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _kind = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return str(value)

    def set(self, name: str, value: str) -> None:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass


def launch_command(
    executable: str = sys.executable, frozen: bool = bool(getattr(sys, "frozen", False))
) -> str:
    """Comando gravado no Run. Congelado: o proprio .exe (igual ao instalador)."""
    if frozen:
        return f'"{executable}"'
    path = PureWindowsPath(executable) if "\\" in executable else PurePosixPath(executable)
    if path.name.lower() == "python.exe":
        path = path.with_name("pythonw.exe")  # sem janela de console
    return f'"{path}" -m pcx_agent'


class AutoStart:
    def __init__(self, store: RunStore, command: str) -> None:
        self._store = store
        self._command = command

    def is_enabled(self) -> bool:
        return self._store.get(VALUE_NAME) == self._command

    def enable(self) -> None:
        self._store.set(VALUE_NAME, self._command)

    def disable(self) -> None:
        self._store.delete(VALUE_NAME)
