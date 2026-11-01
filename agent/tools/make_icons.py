"""Gera os icones do agente a partir de mobile/assets/icon.png (o mesmo desenho do app).

Uso: python tools/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "mobile" / "assets" / "icon.png"
OUT = ROOT / "agent" / "pcx_agent" / "assets"
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
# Recorte quadrado em volta do monitor: o icone do app tem margem de icone adaptativo do
# Android, que deixaria o desenho minusculo na bandeja (16 px).
CROP = (172, 160, 852, 840)
CORNER = 0.2


def rounded(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    mask = Image.new("L", image.size, 0)
    radius = int(image.size[0] * CORNER)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=radius, fill=255)
    image.putalpha(mask)
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as source:
        base = rounded(source.crop(CROP).resize((256, 256), Image.Resampling.LANCZOS))
    base.save(OUT / "icon.ico", sizes=[(s, s) for s in ICO_SIZES])
    base.resize((64, 64), Image.Resampling.LANCZOS).save(OUT / "tray.png")
    print(f"Ícones gravados em {OUT}")


if __name__ == "__main__":
    main()
