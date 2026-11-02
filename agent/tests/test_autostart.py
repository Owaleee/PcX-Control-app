"""Iniciar com o Windows: valor PcXControl na chave Run do usuario."""

import sys

import pytest

from pcx_agent.winsys.autostart import RUN_KEY, VALUE_NAME, AutoStart, launch_command


class DictStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


EXE = "C:\\Users\\owale\\AppData\\Local\\Programs\\PcX Control\\PcXControl.exe"


def test_constants_match_installer():
    assert RUN_KEY == r"Software\Microsoft\Windows\CurrentVersion\Run"
    assert VALUE_NAME == "PcXControl"


def test_enable_writes_quoted_exe_when_frozen():
    store = DictStore()
    AutoStart(store, launch_command(EXE, frozen=True)).enable()
    assert store.values == {"PcXControl": f'"{EXE}"'}


def test_dev_command_uses_pythonw():
    command = launch_command("C:\\Python313\\python.exe", frozen=False)
    assert command == '"C:\\Python313\\pythonw.exe" -m pcx_agent'


def test_dev_command_keeps_pythonw():
    command = launch_command("C:\\venv\\Scripts\\pythonw.exe", frozen=False)
    assert command == '"C:\\venv\\Scripts\\pythonw.exe" -m pcx_agent'


def test_enabled_only_when_value_matches():
    store = DictStore()
    store.set(VALUE_NAME, '"D:\\Antigo\\PcXControl.exe"')
    auto = AutoStart(store, launch_command(EXE, frozen=True))
    assert not auto.is_enabled()
    auto.enable()
    assert auto.is_enabled()


def test_disable_is_idempotent():
    store = DictStore()
    auto = AutoStart(store, launch_command(EXE, frozen=True))
    auto.disable()
    auto.enable()
    auto.disable()
    auto.disable()
    assert store.values == {}
    assert not auto.is_enabled()


@pytest.mark.windows
@pytest.mark.skipif(sys.platform != "win32", reason="registro do Windows")
def test_registry_roundtrip():
    from pcx_agent.winsys.autostart import WinRegistryRunStore

    store = WinRegistryRunStore()
    name = "PcXControlTeste"
    try:
        store.set(name, '"C:\\teste.exe"')
        assert store.get(name) == '"C:\\teste.exe"'
        store.delete(name)
        assert store.get(name) is None
        store.delete(name)
    finally:
        store.delete(name)
