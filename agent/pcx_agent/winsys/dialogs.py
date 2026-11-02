"""Mensagem simples para o usuario, antes de existir qualquer janela do agente."""

import sys

MB_OK = 0x0
MB_ICONERROR = 0x10
MB_ICONINFORMATION = 0x40


def show_message(title: str, text: str, *, error: bool = False) -> None:
    if sys.platform == "win32":
        import ctypes

        flags = MB_OK | (MB_ICONERROR if error else MB_ICONINFORMATION)
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
        return
    if sys.stderr is not None:
        print(f"{title}: {text}", file=sys.stderr)
