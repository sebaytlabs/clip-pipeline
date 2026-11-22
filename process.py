#!/usr/bin/env python3
"""Turns one finished recording into everything that gets posted.

  process.py <recording.mp4> <kind> <name>        kind: gameplay | reading | screen | general

Makes <root>/ready/<date>_<kind>_<name>/ with:
  full.mp4        the whole recording, untouched (the YouTube video)
  thumb.jpg       a frame with the title on it
  short_NN.mp4    vertical 1080x1920 clips for YouTube Shorts, Instagram Reels and Facebook Reels
  post.json       every title, description and caption, and where each piece stands (read by post.py and status.py)

Clips by kind: gameplay and screen videos get up to 58 seconds each, spread evenly through the video (nothing from
only the first minutes); a reading session gets the whole sitting sped up to about 45 seconds, plus one real-time
piece from the middle. Encoding runs at the lowest priority and waits while OBS is recording, so a game being
recorded never stutters because of it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402
import templates  # noqa: E402

ROOT = config.root()
READY, RECORDINGS = os.path.join(ROOT, "ready"), os.path.join(ROOT, "recordings")
FONT = os.environ.get("CLIP_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
CLIP_S = 58          # under a minute: fits Shorts, Reels and Facebook Reels alike
LAPSE_S = 45         # how long a sped-up reading session runs
PLAN = {"gameplay": (6, 120), "screen": (4, 90), "general": (4, 90)}  # kind: (most clips, one clip per this many seconds)
NICE = ["nice", "-n", "19", "ionice", "-c", "3"]


def run(cmd, quiet=True):
    return subprocess.run(cmd, check=True, capture_output=quiet, text=True)


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout.strip()
    return float(out or 0)


def recording_now(root=RECORDINGS, within=20):
    """True while OBS is writing a recording (a file there changed in the last few seconds)."""
    now = time.time()
    for d, _, files in os.walk(root):
        for f in files:
            try:
                if f.endswith(".mp4") and now - os.path.getmtime(os.path.join(d, f)) < within:
                    return True
            except OSError:
                pass
    return False


def wait_until_idle():
    while recording_now():
        time.sleep(30)


def safe(name):
    return re.sub(r"\s+", " ", re.sub(r'[/\\:*?"<>|]', " ", name)).strip()[:80] or "video"


def starts(total, kind):
    """Where each real-time clip begins: evenly spread, never the very first seconds."""
    most, per = PLAN.get(kind, PLAN["general"])
    if total <= CLIP_S + 10:
        return [0.0]
    n = max(1, min(most, int(total // per)))
    return [max(0.0, min(total - CLIP_S, (i + 0.5) * total / n - CLIP_S / 2)) for i in range(n)]


def overlay_file(folder, text):
    """The title as up to three centred lines, in a file ffmpeg reads (no quoting problems: the file sits in the
    temp folder, whose path has no spaces or quotes, whatever the video is called)."""
    import tempfile
    lines = textwrap.wrap(text, 22)[:3]
    fd, path = tempfile.mkstemp(prefix="clip-title-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path, len(lines)


def vertical_filter(kind, title_file, lines, speed=1.0):
    """16:9 in, 1080x1920 out: the picture whole over a blurred copy of itself, the title above it and the
    handle below. A reading session uses the camera's part of the frame, so the book fills the width."""
    # sped up: keep one frame in every `speed` before anything else, so the blur and overlay only work on those
    lapse = f"select='not(mod(n,{max(2, round(speed))}))',setpts=N/(30*TB)," if speed > 1 else ""
    src = f"[0:v]{lapse}" + ("crop=1440:1080:240:0" if kind == "reading" else "null")
    pic_h = 810 if kind == "reading" else 608
    top = (1920 - pic_h) // 2
    ty = max(60, top - 60 - lines * 78)
    return (f"{src},split[a][b];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,eq=brightness=-0.12[bg];"
            "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"drawtext=fontfile={FONT}:textfile='{title_file}':fontcolor=white:fontsize=64:line_spacing=14:"
            f"borderw=4:bordercolor=black@0.85:x=(w-text_w)/2:y={ty},"
            f"drawtext=fontfile={FONT}:text='{handle()}':fontcolor=white@0.9:fontsize=40:borderw=3:"
            f"bordercolor=black@0.8:x=(w-text_w)/2:y={top + pic_h + 46},format=yuv420p")


def handle():
    """The @handle for the bottom of each clip, with characters ffmpeg's drawtext treats as special escaped."""
    h = config.load()["brand"]["handle"]
    return re.sub(r"([\\:'%])", r"\\\1", h)


def encode(src, out, vf, start=None, length=None, audio=True):
    wait_until_idle()
    cmd = NICE + ["ffmpeg", "-y", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.2f}", "-t", f"{length:.2f}"]
    cmd += ["-i", src, "-filter_complex", vf, "-c:v", "libx264", "-crf", "21", "-preset", "veryfast", "-r", "30"]
    cmd += ["-c:a", "aac", "-b:a", "160k"] if audio else ["-an"]
    run(cmd + ["-movflags", "+faststart", out])


def make_shorts(src, folder, kind, overlay, total):
    title_file, lines = overlay_file(folder, overlay)
    made = []
    if kind == "reading":
        speed = max(1.0, total / LAPSE_S)
        if speed > 1.5:  # the whole sitting in under a minute
            out = os.path.join(folder, f"short_{len(made) + 1:02d}.mp4")
            encode(src, out, vertical_filter(kind, title_file, lines, speed), audio=False)
            made.append((out, f"sped up {speed:.0f}x"))
        mid = max(0.0, total / 2 - 22)
        out = os.path.join(folder, f"short_{len(made) + 1:02d}.mp4")
        encode(src, out, vertical_filter(kind, title_file, lines), start=mid, length=min(45, total), audio=False)
        made.append((out, "real time"))
    else:
        for s in starts(total, kind):
            out = os.path.join(folder, f"short_{len(made) + 1:02d}.mp4")
            encode(src, out, vertical_filter(kind, title_file, lines), start=s, length=min(CLIP_S, total))
            made.append((out, f"from {int(s // 60)}:{int(s % 60):02d}"))
    os.remove(title_file)
    return made


def thumbnail(src, folder, kind, title, total):
    """A frame from a quarter of the way in, darkened at the bottom, with the title on it."""
    from PIL import Image, ImageDraw, ImageFont
    raw = os.path.join(folder, ".frame.jpg")
    crop = "crop=1440:1080:240:0,scale=1280:-2,crop=1280:720" if kind == "reading" else "scale=1280:720"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(total * 0.25, max(0, total - 1)):.2f}", "-i", src,
         "-frames:v", "1", "-vf", crop, "-q:v", "2", raw])
    img = Image.open(raw).convert("RGB")
    shade = Image.new("L", (1, 720))
    for y in range(720):
        shade.putpixel((0, y), int(max(0, (y - 300) / 420) ** 1.3 * 215))
    img.paste(Image.new("RGB", img.size, (4, 8, 24)), (0, 0), shade.resize(img.size))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 76)
    lines = textwrap.wrap(title, 24)[:3]
    y = 720 - 70 - len(lines) * 88
    for line in lines:
        d.text((60, y), line, font=font, fill="white", stroke_width=5, stroke_fill=(0, 0, 0))
        y += 88
    d.text((60, 720 - 58), config.load()["brand"]["name"].upper(), font=ImageFont.truetype(FONT, 28), fill=(214, 170, 92))
    out = os.path.join(folder, "thumb.jpg")
    img.save(out, quality=90)
    os.remove(raw)
    return out


def process(src, kind, name):
    t = templates.texts(kind, name)
    total = duration(src)
    folder = os.path.join(READY, f"{date.today().isoformat()}_{kind}_{safe(t['title'])}")
    n = 2
    while os.path.exists(folder):  # the same name twice in a day: both are kept
        folder = os.path.join(READY, f"{date.today().isoformat()}_{kind}_{safe(t['title'])} ({n})")
        n += 1
    os.makedirs(folder)
    full = os.path.join(folder, "full.mp4")
    shutil.move(src, full)  # the recording itself, not a copy: nothing is re-encoded and no disk is used twice
    post = {"kind": kind, "name": name, "title": t["title"], "made": date.today().isoformat(), "seconds": round(total),
            "youtube": {"file": "full.mp4", "thumb": "thumb.jpg", "category": t["category"], **t["youtube"], "status": "ready"},
            "shorts": []}
    save(folder, post)  # written first: if the clips fail, the video and its texts are still there
    thumbnail(full, folder, kind, t["title"], total)
    for path, what in make_shorts(full, folder, kind, t["overlay"], total):
        post["shorts"].append({"file": os.path.basename(path), "what": what,
                               "youtube": dict(t["short"]), "instagram": t["instagram"], "facebook": t["facebook"],
                               "status": {"youtube": "ready", "instagram": "ready", "facebook": "ready"}})
        save(folder, post)
    return folder


def save(folder, post):
    tmp = os.path.join(folder, ".post.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(post, f, indent=1, ensure_ascii=False)
    os.replace(tmp, os.path.join(folder, "post.json"))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    print(process(sys.argv[1], sys.argv[2], sys.argv[3]))
