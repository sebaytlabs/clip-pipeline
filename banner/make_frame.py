#!/usr/bin/env python3
"""Draws the frame the camera sits in for reading sessions: the banner's colours, softened, with the camera's
place left clear in the middle (1440x1080 at x=240) and the name down the sides. Output: reading-frame.png.
Usage: make_frame.py"""
from pathlib import Path

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = Path(__file__).parent
W, H, SIDE = 1920, 1080, 240
FONT_DIR = "/usr/share/fonts/opentype/urw-base35/"


def side_text(text, font, fill):
    """Text turned to read bottom-to-top, for a 240 px side strip."""
    box = font.getbbox(text)
    img = Image.new("RGBA", (box[2] - box[0] + 20, box[3] - box[1] + 30), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((10 - box[0], 10 - box[1]), text, font=font, fill=fill)
    return img.rotate(90, expand=True)


def re_site():
    """The site without https:// for printing, or the handle when there's no site."""
    b = config.load()["brand"]
    return (b["site"].split("//")[-1].rstrip("/")) or b["handle"]


def main():
    base = Image.open(HERE / "reading-banner.png").convert("RGB").filter(ImageFilter.GaussianBlur(90))
    base = ImageEnhance.Brightness(base).enhance(0.55)
    d = ImageDraw.Draw(base)
    d.rectangle([SIDE - 4, 0, W - SIDE + 3, H], fill=(4, 8, 24))  # behind the camera: dark, so no glow shows at its edges
    for x in (SIDE - 4, W - SIDE):  # a thin gold line each side of the picture
        d.rectangle([x, 0, x + 3, H], fill=(214, 170, 92))
    title = side_text("Reading session", ImageFont.truetype(FONT_DIR + "C059-BdIta.otf", 84), (255, 255, 255, 255))
    base.paste(title, ((SIDE - 4 - title.width) // 2, (H - title.height) // 2), title)
    brand = side_text(" ".join(config.load()["brand"]["name"].upper()).replace("   ", "   "), ImageFont.truetype(FONT_DIR + "NimbusSans-Bold.otf", 30), (190, 200, 255, 255))
    site = side_text(re_site(), ImageFont.truetype(FONT_DIR + "NimbusSans-Regular.otf", 34), (214, 220, 255, 255))
    x0 = W - SIDE + 4
    base.paste(brand, (x0 + (SIDE - 4) // 2 - brand.width - 14, (H - brand.height) // 2), brand)
    base.paste(site, (x0 + (SIDE - 4) // 2 + 14, (H - site.height) // 2), site)
    base.save(HERE / "reading-frame.png")
    print(HERE / "reading-frame.png")


if __name__ == "__main__":
    main()
