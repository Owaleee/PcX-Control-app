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


def test_alert_tray_png_exists():
    assert assets_path("tray-alert.png").is_file()


def test_alert_icon_asset_exists_and_same_size():
    with Image.open(assets_path("tray.png")) as normal, Image.open(assets_path("tray-alert.png")) as alert:
        assert alert.size == normal.size
        assert alert.mode == "RGBA"
        corner = (alert.width - 6, alert.height - 6)
        assert alert.getpixel(corner) != normal.getpixel(corner)
