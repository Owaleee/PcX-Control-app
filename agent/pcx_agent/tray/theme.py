"""Cores, fontes e tamanhos da interface da bandeja. Mude o visual por aqui.

As cores sao as do tema escuro do app (mobile/src/theme/themes.ts); um teste avisa se
os dois lados ficarem diferentes. Este modulo nao importa tkinter (e testado no Linux).
"""

COLORS = {
    "background": "#0F172A",
    "titlebar": "#0B1220",
    "surface": "#1E293B",
    "border": "#334155",
    "border_strong": "#475569",
    "text": "#F8FAFC",
    "text_muted": "#CBD5E1",
    "accent": "#38BDF8",
    "accent_hover": "#7DD3FC",
    "on_accent": "#0F172A",
    "danger": "#FDA4AF",
    "selected": "#12304A",
    "qr_background": "#FFFFFF",
}

FONTS = {
    "body": ("Segoe UI", 10),
    "body_bold": ("Segoe UI Semibold", 10),
    "small": ("Segoe UI", 9),
    "title": ("Segoe UI Semibold", 15),
    "step": ("Segoe UI Semibold", 9),
    "mono": ("Cascadia Mono", 11),
}

SPACE = (4, 8, 16, 24, 32)
PADDING = SPACE[4]  # margem interna das janelas
GAP = SPACE[2]  # espaco entre blocos

WINDOW_SIZES = {
    "first_run": (460, 520),
    "pairing": (460, 640),
    "devices": (640, 460),
    "password": (460, 460),
}

QR_SIZE = 264
QR_PANEL = 300  # quadro branco em volta do QR


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """Contraste WCAG entre duas cores #RRGGBB (1 a 21), mesma formula do app."""
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)
