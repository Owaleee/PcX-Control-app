"""Icones do agente, gerados de mobile/assets/icon.png (o mesmo desenho do app)."""

from PIL import Image

from pcx_agent import assets_path

ICO_SIZES = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}


def test_ico_has_all_sizes():
    with Image.open(assets_path("icon.ico")) as ico:
        assert ICO_SIZES <= set(ico.info["sizes"])


def test_tray_png_is_64_rgba():
    with Image.open(assets_path("tray.png")) as png:
        assert png.size == (64, 64)
        assert png.mode == "RGBA"


def test_assets_path_points_to_existing_files():
    assert assets_path("icon.ico").is_file()
    assert assets_path("tray.png").is_file()
