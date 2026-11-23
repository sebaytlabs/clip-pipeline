#!/usr/bin/env python3
"""Draws the reading-session banner shown in OBS instead of a black screen.
Original artwork: a glowing open book with ribbons of light. Output: reading-banner.png (1920x1080).
Usage: make_banner.py [output.png]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
S = 2  # draw at 2x, shrink at the end for smooth edges
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("reading-banner.png")

FONT_DIR = "/usr/share/fonts/opentype/urw-base35/"
TITLE_FONT = FONT_DIR + "C059-BdIta.otf"
LABEL_FONT = FONT_DIR + "NimbusSans-Bold.otf"
SMALL_FONT = FONT_DIR + "NimbusSans-Regular.otf"


def px(v):
    return int(round(v * S))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background():
    """Deep navy at the top, violet toward the bottom, with a bright pool behind the book."""
    strip = Image.new("RGB", (1, 256))
    top, mid, bot = (6, 14, 40), (22, 24, 94), (74, 40, 150)
    for y in range(256):
        t = y / 255
        strip.putpixel((0, y), lerp(top, mid, t / 0.55) if t < 0.55 else lerp(mid, bot, (t - 0.55) / 0.45))
    img = strip.resize((W * S, H * S), Image.BILINEAR)

    pool = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(pool)
    cx, cy = px(960), px(690)
    d.ellipse([cx - px(560), cy - px(300), cx + px(560), cy + px(300)], fill=(70, 90, 230))
    d.ellipse([cx - px(300), cy - px(150), cx + px(300), cy + px(150)], fill=(150, 170, 255))
    pool = pool.filter(ImageFilter.GaussianBlur(px(140)))
    return ImageChops.add(img, pool)


def ribbons(size):
    """Flowing strands of light rising from the book and fanning out."""
    layer = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    strands = 15
    for k in range(strands):
        spread = (k - (strands - 1) / 2) / ((strands - 1) / 2)  # -1 .. 1
        phase = k * 0.55
        pts = []
        for i in range(0, 241):
            t = i / 240
            y = 650 - t * 700
            x = 960 + spread * (60 + 760 * t ** 1.15) + math.sin(t * 5.2 + phase) * (34 + 70 * t)
            pts.append((px(x), px(y)))
        strength = 1 - abs(spread) * 0.55
        base = lerp((60, 80, 200), (170, 200, 255), strength)
        # fade out well below the title so the words stay clean
        for i in range(len(pts) - 1):
            t = i / 240
            fade = 1.0 if t < 0.34 else max(0.0, 1 - (t - 0.34) / 0.2)
            if fade <= 0:
                break
            d.line([pts[i], pts[i + 1]], fill=tuple(int(c * fade) for c in base), width=px(2.2))
    glow = layer.filter(ImageFilter.GaussianBlur(px(7)))
    return ImageChops.add(layer, glow)


def book():
    """Open book seen from the front, pages glowing white-blue."""
    layer = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sx, sy = 960, 700  # spine centre

    def page(side):
        k = -1 if side == "L" else 1
        top = [(sx, sy - 60), (sx + k * 70, sy - 92), (sx + k * 190, sy - 110), (sx + k * 320, sy - 104), (sx + k * 430, sy - 78)]
        bottom = [(sx + k * 435, sy + 62), (sx + k * 320, sy + 38), (sx + k * 190, sy + 30), (sx + k * 70, sy + 42), (sx, sy + 78)]
        return top + bottom

    # page block underneath: a few offset sheets
    for off in (22, 16, 10, 5):
        for side in ("L", "R"):
            pts = [(x, y + off) for x, y in page(side)]
            d.polygon([(px(x), px(y)) for x, y in pts], fill=(120, 140, 220, 255))
    for side in ("L", "R"):
        pts = [(px(x), px(y)) for x, y in page(side)]
        d.polygon(pts, fill=(236, 242, 255, 255))
        d.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=px(2))
    # text lines on the pages
    for side, k in (("L", -1), ("R", 1)):
        for j in range(7):
            y0 = sy - 66 + j * 17
            x1 = sx + k * 52
            x2 = sx + k * (380 - j * 4)
            d.line([(px(x1), px(y0 + abs(k * 0) )), (px(x2), px(y0 + 8))], fill=(150, 165, 215, 255), width=px(3))
    # spine shadow
    d.line([(px(sx), px(sy - 60)), (px(sx), px(sy + 78))], fill=(110, 125, 200, 255), width=px(3))

    glow = layer.filter(ImageFilter.GaussianBlur(px(30)))
    return layer, glow


def spaced(draw, xy, text, font, fill, spacing):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing


def re_site():
    """The site without https:// for printing, or the handle when there's no site."""
    b = config.load()["brand"]
    return (b["site"].split("//")[-1].rstrip("/")) or b["handle"]


def main():
    img = background()
    img = ImageChops.add(img, ribbons(img.size))

    page_layer, glow = book()
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, page_layer)

    d = ImageDraw.Draw(img)
    label = ImageFont.truetype(LABEL_FONT, px(26))
    title = ImageFont.truetype(TITLE_FONT, px(128))
    small = ImageFont.truetype(SMALL_FONT, px(30))

    text = config.load()["brand"]["name"].upper()
    spacing = px(10)
    width = sum(d.textlength(c, font=label) + spacing for c in text) - spacing
    spaced(d, ((W * S - width) / 2, px(78)), text, label, (170, 190, 255, 255), spacing)

    t = "Reading session"
    tw = d.textlength(t, font=title)
    d.text(((W * S - tw) / 2 + px(3), px(122) + px(3)), t, font=title, fill=(10, 14, 60, 200))
    d.text(((W * S - tw) / 2, px(122)), t, font=title, fill=(255, 255, 255, 255))

    d.text((px(70), px(H - 92)), re_site(), font=small, fill=(190, 205, 255, 255))

    img = img.convert("RGB").resize((W, H), Image.LANCZOS)
    img.save(OUT, optimize=True)
    print(OUT)


main()
