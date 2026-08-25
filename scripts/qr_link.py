"""Операция qr_link: PNG с QR-кодом переданной ссылки, файл qr.png в cwd."""
import sys

import qrcode

qr = qrcode.QRCode(border=2, box_size=8)
qr.add_data(sys.argv[1])
qr.make(fit=True)
qr.make_image(fill_color="black", back_color="white").save("qr.png")
print("qr.png")
