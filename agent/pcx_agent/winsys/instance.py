"""Instancia unica do agente: mutex nomeado no Windows, flock nos demais sistemas."""

import sys
from pathlib import Path

# O instalador (AppMutex) usa o mesmo nome para pedir que o agente seja fechado.
MUTEX_NAME = "Local\\PcXControl.Agent"
LOCK_FILE = "agent.lock"


class InstanceLock:
    def __init__(self, release_fn) -> None:
        self._release_fn = release_fn

    def release(self) -> None:
        if self._release_fn is not None:
            self._release_fn()
            self._release_fn = None


def _acquire_windows() -> InstanceLock | None:
    import win32api
    import win32event
    import winerror

    handle = win32event.CreateMutex(None, False, MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        win32api.CloseHandle(handle)
        return None
    return InstanceLock(lambda: win32api.CloseHandle(handle))


def _acquire_posix(data_dir: Path) -> InstanceLock | None:
    import fcntl

    data_dir.mkdir(parents=True, exist_ok=True)
    handle = open(data_dir / LOCK_FILE, "a")  # noqa: SIM115 - fica aberto enquanto o agente roda
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None

    def release() -> None:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()

    return InstanceLock(release)


def acquire_single_instance(data_dir: Path) -> InstanceLock | None:
    """Trava de instancia unica, ou None se outro agente ja estiver rodando."""
    if sys.platform == "win32":
        return _acquire_windows()
    return _acquire_posix(Path(data_dir))
