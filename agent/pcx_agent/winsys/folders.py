"""Pastas conhecidas do Windows (Area de Trabalho, Documentos) e "mostrar no Explorador"."""

import subprocess
import sys
from pathlib import Path

_FOLDER_IDS = {
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",  # FOLDERID_Desktop
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",  # FOLDERID_Documents
}


def _known_folder(name: str) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8),
            ]

        raw = uuid.UUID(_FOLDER_IDS[name])
        guid = GUID(raw.time_low, raw.time_mid, raw.time_hi_version, (ctypes.c_ubyte * 8)(*raw.bytes[8:]))
        out = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p),
        ]
        if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return Path(out.value) if out.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)
    except Exception:  # noqa: BLE001 - sem a pasta, o pacote cai para a proxima
        return None


def desktop_dir() -> Path | None:
    return _known_folder("desktop")


def documents_dir() -> Path | None:
    return _known_folder("documents")


def reveal(path: Path) -> None:
    """Abre o Explorador com o arquivo selecionado."""
    if sys.platform != "win32":
        return
    try:
        # Uma string so: o Explorador quer `/select,"caminho"` com as aspas dentro do argumento.
        subprocess.Popen(f'explorer /select,"{path}"')
    except OSError:
        pass
