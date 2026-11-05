"""Gera os icones do agente a partir de mobile/assets/icon.png (o mesmo desenho do app).

Uso: python tools/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

from pcx_agent.tray.theme import COLORS

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "mobile" / "assets" / "icon.png"
OUT = ROOT / "agent" / "pcx_agent" / "assets"
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
# Recorte quadrado em volta do monitor: o icone do app tem margem de icone adaptativo do
# Android, que deixaria o desenho minusculo na bandeja (16 px).
CROP = (172, 160, 852, 840)
CORNER = 0.2
ALERT_DOT = 0.3


def rounded(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    mask = Image.new("L", image.size, 0)
    radius = int(image.size[0] * CORNER)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=radius, fill=255)
    image.putalpha(mask)
    return image


def with_alert_dot(tray: Image.Image) -> Image.Image:
    """O icone da bandeja com um circulo de alerta (30% do lado) no canto inferior direito."""
    size = tray.size[0]
    diameter = round(size * ALERT_DOT)
    border = 2
    right = size - 1
    box = (right - diameter, right - diameter, right, right)
    out = tray.copy()
    draw = ImageDraw.Draw(out)
    draw.ellipse(box, fill=COLORS["background"])  # contorno de 2 px da cor de fundo
    draw.ellipse(
        (box[0] + border, box[1] + border, box[2] - border, box[3] - border), fill=COLORS["danger"]
    )
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as source:
        base = rounded(source.crop(CROP).resize((256, 256), Image.Resampling.LANCZOS))
    base.save(OUT / "icon.ico", sizes=[(s, s) for s in ICO_SIZES])
    tray = base.resize((64, 64), Image.Resampling.LANCZOS)
    tray.save(OUT / "tray.png")
    with_alert_dot(tray).save(OUT / "tray-alert.png")
    print(f"Ícones gravados em {OUT}")


if __name__ == "__main__":
    main()
