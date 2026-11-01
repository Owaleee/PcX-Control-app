"""QR code de pareamento como imagem para o tkinter."""

import qrcode
from PIL import Image, ImageTk

from pcx_agent.tray.theme import COLORS, QR_SIZE


def qr_image(uri: str, size: int = QR_SIZE) -> Image.Image:
    qr = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(uri)
    image = qr.make_image(fill_color=COLORS["background"], back_color=COLORS["qr_background"])
    return image.get_image().convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def qr_photo(uri: str, size: int = QR_SIZE) -> ImageTk.PhotoImage:
    return ImageTk.PhotoImage(qr_image(uri, size))
