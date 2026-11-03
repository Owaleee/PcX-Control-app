"""Tema e textos da bandeja: mesmas cores do app, contraste legivel, textos num lugar so."""

import re
from pathlib import Path

import pytest

from pcx_agent.tray import texts
from pcx_agent.tray.theme import COLORS, WINDOW_SIZES, contrast_ratio

APP_THEMES = Path(__file__).resolve().parents[2] / "mobile" / "src" / "theme" / "themes.ts"


def _app_dark_theme() -> dict[str, str]:
    source = APP_THEMES.read_text(encoding="utf-8")
    block = re.search(r"dark:\s*\{(.*?)\}", source, re.DOTALL).group(1)
    return dict(re.findall(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'", block))


@pytest.mark.parametrize(
    ("ours", "app"),
    [
        ("background", "background"),
        ("surface", "surface"),
        ("text", "text"),
        ("text_muted", "textMuted"),
        ("accent", "accent"),
        ("danger", "danger"),
        ("warning", "warning"),
        ("border", "border"),
    ],
)
def test_colors_match_app_dark_theme(ours, app):
    assert COLORS[ours].upper() == _app_dark_theme()[app].upper()


@pytest.mark.parametrize(
    ("fg", "bg"),
    [
        ("text", "background"),
        ("text", "surface"),
        ("text_muted", "background"),
        ("text_muted", "surface"),
        ("text_muted", "selected"),
        ("accent", "selected"),
        ("on_accent", "accent"),
        ("danger", "background"),
        ("text", "titlebar"),
        ("ok", "background"),
        ("ok", "surface"),
        ("warning", "background"),
        ("warning", "surface"),
        ("danger", "surface"),
    ],
)
def test_text_contrast_is_readable(fg, bg):
    assert contrast_ratio(COLORS[fg], COLORS[bg]) >= 4.5


def test_contrast_ratio_extremes():
    assert round(contrast_ratio("#FFFFFF", "#000000"), 1) == 21.0
    assert contrast_ratio("#0F172A", "#0F172A") == 1.0


def test_window_sizes_follow_the_mockup():
    assert WINDOW_SIZES == {
        "first_run": (460, 520),
        "first_run_pair": (460, 720),
        "pairing": (460, 640),
        "devices": (640, 460),
        "password": (460, 460),
        "diagnostics": (560, 640),
    }


def test_texts_are_plain_strings():
    public = {k: v for k, v in vars(texts).items() if k.isupper()}
    assert len(public) >= 30
    assert all(isinstance(v, str) and v.strip() for v in public.values())


def test_text_templates_format():
    assert texts.VALID_FOR.format(tempo="4:37") == "Vale por 4:37"
    assert texts.PAIRED.format(nome="Poco X7 Pro") == "Celular Poco X7 Pro pareado!"
    assert texts.NOTIFY_PAIRED.format(nome="Poco") == "Celular Poco pareado."
    assert "{" not in texts.MENU_PAIR
