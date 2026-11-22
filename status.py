#!/usr/bin/env python3
"""The weekly check, as one spreadsheet: <root>/Posting.xlsx, rebuilt after every recording and
every posting run. First sheet: what needs you (normally nothing). Second: every video and clip and where it stands.

  python3 status.py          rebuild it
  python3 status.py --open   rebuild it and open it
"""
import glob
import json
import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = config.root()
OUT = os.path.join(ROOT, "Posting.xlsx")
NAVY = "14264D"
head = Font(name="Arial", size=10, bold=True, color="FFFFFF")
fill = PatternFill("solid", fgColor=NAVY)
COLORS = {"posted": "D9EAD3", "scheduled": "FFF2CC", "ready": "FFFFFF", "failed": "F4CCCC", "needs you": "F4CCCC"}


def videos():
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "ready", "*", "post.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                out.append((os.path.dirname(path), json.load(f)))
        except (OSError, ValueError):
            continue
    return out


def state(s):
    """'scheduled Thu Nov 12 6:00 PM' from a status value (a word, or {"state", "when", "why"})."""
    if isinstance(s, str):
        return s, ""
    word = s.get("state", "ready")
    when = s.get("when", "")
    try:
        when = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().strftime("%a %b %-d %-I:%M %p") if when else ""
    except ValueError:
        pass
    return word, when or s.get("why", "")


def waiting_recordings():
    """Recordings nobody named yet: they sit in recordings/ until they have a name."""
    out = []
    for d, _, files in os.walk(os.path.join(ROOT, "recordings")):
        out += [os.path.join(d, f) for f in files if f.endswith(".mp4")]
    return out


def needs_you(vids, setup):
    rows = [(what, how) for what, how in setup]
    for path in waiting_recordings():
        rows.append((f"A recording has no name yet: {os.path.basename(path)}",
                     f"Rename it in {os.path.dirname(path)} to its title; it's picked up by itself."))
    for folder, p in vids:
        word, why = state(p["youtube"].get("status", "ready"))
        if word in ("failed", "needs you"):
            rows.append((f"{p['title']}: the full video didn't upload", why))
        for s in p["shorts"]:
            for site, st in s["status"].items():
                word, why = state(st)
                if word == "failed":
                    rows.append((f"{p['title']}: {s['file']} didn't post to {site}", why))
    return rows


def build(setup=()):
    vids = videos()
    wb = Workbook()
    ws = wb.active
    ws.title = "Needs you"
    ws["A1"] = f"{config.load()['brand']['name']} posting: what needs you"
    ws["A1"].font = Font(name="Arial", size=16, bold=True, color=NAVY)
    ws["A2"] = f"Checked {datetime.now():%A %B %-d, %-I:%M %p}. {len(vids)} videos made so far."
    rows = needs_you(vids, setup)
    for c, t in enumerate(("What", "What to do"), 1):
        cell = ws.cell(4, c, t)
        cell.font, cell.fill = head, fill
    if not rows:
        ws.cell(5, 1, "Nothing. Everything recorded is posted or on the schedule.")
    for i, (what, how) in enumerate(rows):
        ws.cell(5 + i, 1, what).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(5 + i, 2, how).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 60, 80

    ws = wb.create_sheet("Everything")
    cols = ("Made", "Kind", "Video", "Piece", "YouTube", "Instagram", "Facebook", "When / why")
    for c, t in enumerate(cols, 1):
        cell = ws.cell(1, c, t)
        cell.font, cell.fill = head, fill
    r = 2
    for folder, p in reversed(vids):
        word, when = state(p["youtube"].get("status", "ready"))
        line = [p["made"], p["kind"], p["title"], "full video", word, "", "", when]
        for c, v in enumerate(line, 1):
            ws.cell(r, c, v)
        ws.cell(r, 5).fill = PatternFill("solid", fgColor=COLORS.get(word, "FFFFFF"))
        r += 1
        for s in p["shorts"]:
            words = {site: state(st) for site, st in s["status"].items()}
            line = ["", "", "", f"{s['file']} ({s.get('what', '')})", words["youtube"][0], words["instagram"][0],
                    words["facebook"][0], next((w for _, w in words.values() if w), "")]
            for c, v in enumerate(line, 1):
                ws.cell(r, c, v)
            for c, site in ((5, "youtube"), (6, "instagram"), (7, "facebook")):
                ws.cell(r, c).fill = PatternFill("solid", fgColor=COLORS.get(words[site][0], "FFFFFF"))
            r += 1
    for col, w in zip("ABCDEFGH", (12, 13, 46, 30, 13, 13, 13, 36)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    tmp = OUT + ".tmp.xlsx"
    wb.save(tmp)
    os.replace(tmp, OUT)
    return OUT, rows


if __name__ == "__main__":
    try:  # what the poster still needs set up, if it's there to ask
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import post
        setup = post.missing_setup()
    except Exception:
        setup = ()
    out, rows = build(setup)
    print(out, f"({len(rows)} need you)")
    if "--open" in sys.argv:
        subprocess.Popen(["xdg-open", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
