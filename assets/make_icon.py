"""Draws the StyleVault icon (blue rounded square + three stacked cards) -> stylevault.png / .ico."""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=230, fill=(47, 91, 255, 255))
for i, (dx, alpha) in enumerate(((-150, 110), (0, 190), (150, 255))):
    x0 = 290 + dx
    d.rounded_rectangle([x0, 250 + (2 - i) * 0, x0 + 320, 250 + 520], radius=44, fill=(255, 255, 255, alpha))
d.rounded_rectangle([440, 300, 760, 360], radius=24, fill=(47, 91, 255, 255))
d.rounded_rectangle([440, 400, 700, 440], radius=18, fill=(190, 205, 255, 255))
d.rounded_rectangle([440, 470, 640, 510], radius=18, fill=(190, 205, 255, 255))
im.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "stylevault.png"))
im.save(os.path.join(HERE, "stylevault.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
