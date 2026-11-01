"""Base das janelas e pecas reutilizaveis.

Regra para as proximas janelas: herdar de `BaseWindow`, usar so cores e fontes de
`theme`, textos de `texts` e regras do `AgentController`. Nenhum arquivo de janela
deve passar de ~150 linhas; se crescer, extraia uma peca para ca.
"""

import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import ClassVar

from pcx_agent import assets_path
from pcx_agent.tray.theme import COLORS, FONTS, GAP, PADDING, SPACE, WINDOW_SIZES

DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def apply_style(root: tk.Tk) -> None:
    """Estilo dos widgets ttk (so a tabela usa ttk). Chamar uma vez."""
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "Pcx.Treeview",
        background=COLORS["background"],
        fieldbackground=COLORS["background"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        rowheight=40,
        font=FONTS["body"],
    )
    style.configure(
        "Pcx.Treeview.Heading",
        background=COLORS["surface"],
        foreground=COLORS["text_muted"],
        bordercolor=COLORS["border"],
        relief="flat",
        font=FONTS["body_bold"],
    )
    style.map("Pcx.Treeview", background=[("selected", COLORS["border_strong"])])
    style.map("Pcx.Treeview.Heading", background=[("active", COLORS["surface"])])


def _dark_title_bar(window: tk.Toplevel) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
    except (AttributeError, OSError):  # Windows antigo: fica a barra clara
        pass


def _set_icon(window: tk.Toplevel) -> None:
    try:
        if sys.platform == "win32":
            window.iconbitmap(str(assets_path("icon.ico")))
        else:
            window._icon = tk.PhotoImage(file=str(assets_path("tray.png")))
            window.iconphoto(False, window._icon)
    except tk.TclError:
        pass


class BaseWindow(tk.Toplevel):
    """Janela do agente: icone, tamanho do tema, centralizada, Esc fecha, Enter confirma."""

    size_key: ClassVar[str]
    title_text: ClassVar[str]
    _open: ClassVar[dict[type, "BaseWindow"]] = {}

    @classmethod
    def show(cls, root: tk.Tk, controller, **kwargs) -> "BaseWindow":
        """Abre uma janela por classe: chamar de novo traz a existente para a frente."""
        current = BaseWindow._open.get(cls)
        if current is not None and current.winfo_exists():
            current.on_reopen()
            current.deiconify()
            current.lift()
            current.focus_force()
            return current
        window = cls(root, controller, **kwargs)
        BaseWindow._open[cls] = window
        return window

    def __init__(self, root: tk.Tk, controller) -> None:
        super().__init__(root, bg=COLORS["background"])
        self.controller = controller
        self.title(self.title_text)
        width, height = WINDOW_SIZES[self.size_key]
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 3
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        _set_icon(self)
        _dark_title_bar(self)
        self.body = tk.Frame(self, bg=COLORS["background"], padx=PADDING, pady=SPACE[3])
        self.body.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<Return>", lambda _e: self.primary_action())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.focus_force()

    def primary_action(self) -> None:
        """Acao do Enter. As janelas sobrescrevem."""

    def on_reopen(self) -> None:
        """Chamado quando `show` encontra a janela ja aberta."""

    def close(self) -> None:
        if BaseWindow._open.get(type(self)) is self:
            del BaseWindow._open[type(self)]
        self.destroy()


def label(parent, text: str, *, font: str = "body", color: str = "text", **kw) -> tk.Label:
    bg = kw.pop("bg", parent["bg"])
    return tk.Label(parent, text=text, font=FONTS[font], fg=COLORS[color], bg=bg, **kw)


def heading(parent, title: str, subtitle: str) -> tk.Frame:
    frame = tk.Frame(parent, bg=parent["bg"])
    label(frame, title, font="title", anchor="w").pack(fill="x")
    label(
        frame, subtitle, color="text_muted", anchor="w", justify="left", wraplength=380
    ).pack(fill="x", pady=(SPACE[0], 0))
    return frame


def _button(parent, text: str, command: Callable[[], None], **colors) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        relief="flat",
        bd=0,
        padx=SPACE[2] + 2,
        pady=SPACE[1] - 2,
        cursor="hand2",
        highlightthickness=1,
        **colors,
    )


def primary_button(parent, text: str, command: Callable[[], None]) -> tk.Button:
    return _button(
        parent, text, command, bg=COLORS["accent"], fg=COLORS["on_accent"],
        activebackground=COLORS["accent_hover"], activeforeground=COLORS["on_accent"],
        highlightbackground=COLORS["accent"], font=FONTS["body_bold"],
    )


def secondary_button(parent, text: str, command: Callable[[], None]) -> tk.Button:
    return _button(
        parent, text, command, bg=COLORS["background"], fg=COLORS["text"],
        activebackground=COLORS["surface"], activeforeground=COLORS["text"],
        highlightbackground=COLORS["border_strong"], font=FONTS["body"],
    )


def danger_button(parent, text: str, command: Callable[[], None]) -> tk.Button:
    return _button(
        parent, text, command, bg=COLORS["background"], fg=COLORS["danger"],
        activebackground=COLORS["surface"], activeforeground=COLORS["danger"],
        highlightbackground=COLORS["danger"], font=FONTS["body"],
    )


class PasswordField(tk.Frame):
    """Rotulo, campo de senha e a linha de erro embaixo."""

    def __init__(self, parent, text: str) -> None:
        super().__init__(parent, bg=parent["bg"])
        label(self, text, color="text_muted", anchor="w").pack(fill="x")
        self.entry = tk.Entry(
            self, show="•", font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief="flat", highlightthickness=1,
            highlightbackground=COLORS["border_strong"], highlightcolor=COLORS["accent"],
        )
        self.entry.pack(fill="x", ipady=SPACE[1] - 1, pady=(SPACE[0], 0))
        self._error = label(self, "", font="small", color="danger", anchor="w")
        self._error.pack(fill="x")

    def value(self) -> str:
        return self.entry.get()

    def set_value(self, text: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def show_error(self, text: str) -> None:
        self._error.configure(text=text)
        self.entry.configure(highlightbackground=COLORS["danger"])

    def clear_error(self) -> None:
        self._error.configure(text="")
        self.entry.configure(highlightbackground=COLORS["border_strong"])

    def error_text(self) -> str:
        return self._error.cget("text")


class InfoPanel(tk.Frame):
    """Caixa com pares rotulo/valor lado a lado."""

    def __init__(self, parent, pairs: list[tuple[str, str]]) -> None:
        super().__init__(
            parent, bg=COLORS["surface"], highlightthickness=1,
            highlightbackground=COLORS["border"], padx=SPACE[2] - 2, pady=SPACE[1] + 2,
        )
        self._values: list[tk.Label] = []
        for column, (title, value) in enumerate(pairs):
            self.columnconfigure(column, weight=1, uniform="info")
            cell = tk.Frame(self, bg=COLORS["surface"])
            cell.grid(row=0, column=column, sticky="w", padx=(0, GAP))
            label(cell, title, font="small", color="text_muted", anchor="w").pack(fill="x")
            font = "mono" if column == 0 else "body"
            value_label = label(cell, value, font=font, anchor="w")
            value_label.pack(fill="x")
            self._values.append(value_label)

    def set_value(self, index: int, text: str) -> None:
        self._values[index].configure(text=text)


def button_row(parent) -> tk.Frame:
    row = tk.Frame(parent, bg=parent["bg"])
    row.pack(side="bottom", fill="x")
    return row
