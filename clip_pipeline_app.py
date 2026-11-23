#!/usr/bin/env python3
"""Clip Pipeline app: set up your channel, record, and see every video and clip in one window.

  python3 clip_pipeline_app.py

Pages: Start here (what's set up and what isn't), My channel (name, handle, links), Record (open OBS on the
right setup), Videos (everything made, with captions to copy), Posting (Buffer, optional).
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import config
from appkit import BG, DIM, FG, FONT, LINE, PANEL, App, Capture, Job, Page, open_path, write

ACCENT = "#c2255c"
HERE = Path(__file__).resolve().parent
UNIT = "clip-watch.service"
UNIT_PATH = Path.home() / ".config/systemd/user" / UNIT
OBS_DIRS = [Path.home() / ".var/app/com.obsproject.Studio/config/obs-studio", Path.home() / ".config/obs-studio"]
ABOUT = ("Clip Pipeline\n\nRecord in OBS and type the video's name. You get the full video, vertical clips for "
         "Shorts and Reels, a thumbnail and every caption, and, if you want, one clip a day posted for you.\n\n"
         "Free and open source (MIT), by Sebayt Labs.")
KINDS = [("gameplay", "Gameplay", "the whole screen and the game's sound, no camera"),
         ("reading", "Reading", "the camera over a banner, silent"),
         ("screen", "Screen", "the whole screen with a small camera in the corner")]


def save_config(updates):
    path = Path(config.CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    for k, v in updates.items():
        if isinstance(v, dict):
            data[k] = {**data.get(k, {}), **v}
        else:
            data[k] = v
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(path, 0o600)


def watcher_state():
    if not shutil.which("systemctl"):
        return "unsupported"
    if not UNIT_PATH.exists():
        return "not installed"
    r = subprocess.run(["systemctl", "--user", "is-active", UNIT], capture_output=True, text=True)
    return "running" if r.stdout.strip() == "active" else "stopped"


def obs_ready():
    return any((d / "basic/profiles/Gameplay/basic.ini").exists() for d in OBS_DIRS)


def videos():
    out = []
    for p in sorted(glob.glob(os.path.join(config.root(), "ready", "*", "post.json")), reverse=True):
        try:
            out.append((Path(p).parent, json.loads(Path(p).read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            pass
    return out


def missing_tools():
    need = {"ffmpeg": "ffmpeg", "inotifywait": "inotify-tools", "zenity": "zenity", "notify-send": "libnotify-bin"}
    return [pkg for cmd, pkg in need.items() if not shutil.which(cmd)]


# ------------------------------------------------------------------ Start here
class StartPage(Page):
    HELP = ("Start here\n\nThis page checks each part of the setup and has a button to fix what's missing. "
            "Work down the list once; after that you only use Record and Videos.")
    HINT = "Work down the checklist once. After that, just record."

    def shown(self):
        self.clear()
        self.title("Start here", "How it works: you record in OBS and type the video's name. Everything else is made "
                                 "for you: the full video, vertical clips, a thumbnail and every caption.")
        brand = config.load()["brand"]
        tools = missing_tools()
        w = watcher_state()
        items = [
            ("Programs it needs", not tools, "ffmpeg, inotify-tools, zenity, libnotify-bin" if tools else "all there",
             None if not tools else ("How to install", lambda: messagebox.showinfo(
                 "Install", "In a terminal:\n\nsudo apt install " + " ".join(tools) +
                 "\n\nOBS: install it from your app store (Flatpak is fine)."))),
            ("Your channel", brand["name"] != "My Channel", brand["name"],
             ("Set it up", lambda: self.app.show("channel"))),
            ("OBS setups", obs_ready(), "Gameplay, Reading and Screen" if obs_ready() else "not made yet",
             ("Set up OBS", lambda: self.app.show("record"))),
            ("Clip maker", w == "running", {"running": "running in the background; recordings are picked up by "
                                                       "themselves", "stopped": "installed but stopped",
                                            "not installed": "not installed", "unsupported": "needs Linux"}[w],
             None if w == "running" else ("Turn it on", self.turn_on)),
        ]
        self.checklist = tk.Frame(self.body, bg=BG)
        self.checklist.pack(fill="x")
        for name, ok, detail, action in items:
            c = self.card(self.checklist)
            tk.Label(c, text="✔" if ok else "•", bg=PANEL, fg="#2f9e44" if ok else ACCENT,
                     font=(FONT, 16, "bold"), width=2).pack(side="left", padx=(12, 4), pady=8)
            tk.Label(c, text=name, bg=PANEL, fg=FG, font=(FONT, 12, "bold"), width=18, anchor="w").pack(side="left")
            tk.Label(c, text=detail, bg=PANEL, fg=DIM, font=(FONT, 11), anchor="w").pack(side="left", fill="x",
                                                                                      expand=True)
            if action:
                self.button(c, action[0], action[1]).pack(side="right", padx=10, pady=6)
        v = videos()
        self.text(f"{len(v)} videos made so far.  Root folder: {config.root()}", 11, DIM, pady=(14, 4))
        r = self.row()
        self.button(r, "Record now", lambda: self.app.show("record")).pack(side="left")
        self.button(r, "See my videos", lambda: self.app.show("videos"), primary=False).pack(side="left", padx=8)

    def turn_on(self):
        tools = missing_tools()
        if tools:
            messagebox.showinfo("Clip maker", "First install: sudo apt install " + " ".join(tools))
            return
        UNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        UNIT_PATH.write_text("[Unit]\nDescription=Clip Pipeline: turn finished OBS recordings into clips\n\n"
                             f"[Service]\nExecStart={HERE / 'watch.sh'}\nRestart=on-failure\nRestartSec=5\n\n"
                             "[Install]\nWantedBy=default.target\n", encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"])
        subprocess.run(["systemctl", "--user", "enable", "--now", UNIT])
        self.app.say("The clip maker is on. It starts by itself when you log in.")
        self.shown()


# ------------------------------------------------------------------ My channel
class ChannelPage(Page):
    HELP = ("My channel\n\nThese go on every thumbnail, clip and caption:\nName: printed on thumbnails.\n"
            "Handle: printed under every clip, like @mychannel.\nYouTube link: used for the Subscribe link.\n"
            "Website and Main link: the one place you want people to go.\nHashtag: your own tag, added to every "
            "post (no #).\n\nVideos folder: where recordings, clips and the status sheet live.")
    HINT = "Fill these in once and press Save."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        c = config.load()
        b = c["brand"]
        self.title("My channel", "Your name and links, printed on every thumbnail and clip and used in every caption.")
        self.vars = {}
        self.fields = tk.Frame(self.body, bg=BG)
        self.fields.pack(fill="x")
        for key, label, hint in (("name", "Channel name", "on thumbnails"), ("handle", "Handle", "like @mychannel"),
                                 ("channel", "YouTube link", "https://www.youtube.com/@…"),
                                 ("site", "Website", "optional"), ("link", "Main link", "optional: the one thing to "
                                                                                       "click"),
                                 ("hashtag", "Your hashtag", "without the #")):
            r = self.row(self.fields)
            tk.Label(r, text=label, bg=BG, fg=FG, font=(FONT, 11), width=16, anchor="w").pack(side="left")
            v = tk.StringVar(value=b.get(key, ""))
            tk.Entry(r, textvariable=v, font=(FONT, 11), relief="solid", bd=1, width=44).pack(side="left", ipady=4)
            tk.Label(r, text=hint, bg=BG, fg=DIM, font=(FONT, 10)).pack(side="left", padx=8)
            self.vars[key] = v
        self.root = tk.StringVar(value=c["root"])
        self.path_field("Videos folder", self.root)
        r = self.row(pady=12)
        self.save_btn = self.button(r, "Save", self.save)
        self.save_btn.pack(side="left")
        self.button(r, "Remake the reading banner", self.banner, primary=False).pack(side="left", padx=8)
        self.msg = self.text("", 11, DIM)

    def save(self):
        brand = {k: v.get().strip() for k, v in self.vars.items()}
        brand["hashtag"] = brand["hashtag"].lstrip("#")
        if brand["handle"] and not brand["handle"].startswith("@"):
            brand["handle"] = "@" + brand["handle"]
        if brand["hashtag"] in ("", config.DEFAULTS["brand"]["hashtag"]) and brand["handle"] not in ("", "@mychannel"):
            brand["hashtag"] = brand["handle"].lstrip("@")      # your own tag follows your handle until you pick one
            self.vars["hashtag"].set(brand["hashtag"])
        save_config({"brand": brand, "root": self.root.get()})
        self.banner(quiet=True)
        self.msg.config(text=f"Saved to {config.CONFIG}. The reading banner was remade with your name.")

    def banner(self, quiet=False):
        for s in ("make_banner.py", "make_frame.py"):
            subprocess.run([sys.executable, str(HERE / "banner" / s)], capture_output=True)
        if not quiet:
            open_path(HERE / "banner")


# ------------------------------------------------------------------ Record
class RecordPage(Page):
    HELP = ("Record\n\n1. The first time, press Set up OBS (close OBS first). It makes three ready setups.\n"
            "2. Press the kind of video you're making. OBS opens on the right setup.\n3. Press Start Recording in "
            "OBS. When you stop, a box asks for the video's name. That's all.\n\nKinds:\nGameplay: the whole screen "
            "and the game's sound.\nReading: the camera over a banner, silent.\nScreen: the whole screen with a "
            "small camera.")
    HINT = "Pick the kind of video. When you stop recording, type its name in the box that pops up."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.title("Record", "OBS opens on the right setup. When you stop recording, you're asked for the name. "
                             "That's the only thing you do.")
        self.steps(["First time only: close OBS and press Set up OBS.",
                    "Press the kind of video below. OBS opens ready.",
                    "Record. When you stop, type the video's name in the box that pops up."])
        self.kinds = tk.Frame(self.body, bg=BG)
        self.kinds.pack(fill="x")
        for key, name, what in KINDS:
            c = self.card(self.kinds)
            tk.Label(c, text=name, bg=PANEL, fg=FG, font=(FONT, 13, "bold"), width=10, anchor="w").pack(side="left",
                                                                                                    padx=14, pady=10)
            tk.Label(c, text=what, bg=PANEL, fg=DIM, font=(FONT, 11)).pack(side="left")
            self.button(c, f"Record {name.lower()}", lambda k=key: self.record(k)).pack(side="right", padx=10)
        r = self.row(pady=14)
        tk.Label(r, text="Encoder", bg=BG, fg=FG, font=(FONT, 11)).pack(side="left")
        self.enc = ttk.Combobox(r, values=["x264 (works everywhere)", "qsv (Intel graphics)", "nvenc (NVIDIA)"],
                                state="readonly", width=26)
        self.enc.current(0)
        self.enc.pack(side="left", padx=8)
        self.button(r, "Set up OBS", self.setup, primary=False).pack(side="left")
        self.file_btn = self.button(r, "Make clips from a file I already have…", self.from_file, primary=False)
        self.file_btn.pack(side="right")
        r = self.row()
        self.sample_btn = self.button(r, "Try it with a sample video", self.sample, primary=False)
        self.sample_btn.pack(side="left")
        tk.Label(r, text="makes a 75-second test video and turns it into clips, so you can see what you get",
                 bg=BG, fg=DIM, font=(FONT, 10)).pack(side="left", padx=8)
        self.log = self.log_box(6)

    def record(self, kind):
        if not obs_ready():
            messagebox.showinfo("Record", "Set up OBS first (button below). Close OBS before you press it.")
            return
        if watcher_state() != "running":
            if not messagebox.askyesno("Record", "The clip maker isn't running, so the recording won't be turned "
                                                 "into clips by itself. Record anyway?"):
                return
        subprocess.Popen(["bash", str(HERE / "obs/record.sh"), kind])
        self.app.say("OBS is opening. Press Start Recording in it.")

    def setup(self):
        enc = ["x264", "qsv", "nvenc"][self.enc.current()]
        r = subprocess.run([sys.executable, str(HERE / "obs/setup_obs.py"), "--encoder", enc], capture_output=True,
                           text=True)
        write(self.log, (r.stdout + r.stderr).strip() + "\n")
        if r.returncode == 0:
            write(self.log, "OBS is set up. The three Record buttons are also in your app menu.\n")

    def make(self, f, kind, name):
        """Copy f into the pipeline and make its clips in the background."""
        copy = Path(config.root()) / "named" / Path(f).name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, copy)   # process.py moves its input; your original stays where it was
        write(self.log, f"Making clips for '{name}'. This takes a minute or more…\n")
        Job(self, self.log, lambda log: subprocess.run([sys.executable, str(HERE / "process.py"), str(copy), kind,
                                                        name], capture_output=True, text=True),
            lambda r: write(self.log, ("Done. See it on the Videos page." if getattr(r, "returncode", 1) == 0
                                       else f"Problem: {getattr(r, 'stderr', r)}") + "\n"))

    def sample(self):
        if not shutil.which("ffmpeg"):
            messagebox.showinfo("Sample", "This needs ffmpeg: sudo apt install ffmpeg")
            return
        import tempfile
        f = Path(tempfile.gettempdir()) / "clip-pipeline-sample.mp4"
        write(self.log, "Making a 75-second test video…\n")
        brand = config.load()["brand"]["name"]

        def work(log):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
                            "-f", "lavfi", "-i", "sine=frequency=330", "-t", "75", "-c:v", "libx264", "-preset",
                            "veryfast", "-c:a", "aac", "-shortest", str(f)], check=True)
        Job(self, self.log, work, lambda r: write(self.log, f"Couldn't make it: {r}\n") if isinstance(
            r, BaseException) else self.make(f, "general", f"Sample video for {brand}"))

    def from_file(self):
        f = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.mov")])
        if not f:
            return
        top = tk.Toplevel(self)
        top.title("Make clips")
        top.configure(bg=BG, padx=20, pady=16)
        tk.Label(top, text="What kind of video is it?", bg=BG, font=(FONT, 11)).pack(anchor="w")
        kind = ttk.Combobox(top, values=[n for _, n, _ in KINDS] + ["Other"], state="readonly")
        kind.current(0)
        kind.pack(fill="x", pady=4)
        tk.Label(top, text="Its name (for a game: Game: what it shows)", bg=BG, font=(FONT, 11)).pack(anchor="w",
                                                                                                   pady=(8, 0))
        name = tk.Entry(top, font=(FONT, 11), width=50)
        name.pack(fill="x", pady=4)

        def go():
            k = ([key for key, _, _ in KINDS] + ["general"])[kind.current()]
            n = name.get().strip()
            if not n:
                return
            top.destroy()
            self.make(f, k, n)
        self.button(top, "Make the clips", go).pack(anchor="e", pady=8)


# ------------------------------------------------------------------ Videos
class VideosPage(Page):
    HELP = ("Videos\n\nEverything the pipeline has made, newest first. For each one: open its folder (full video, "
            "clips, thumbnail), or see the captions for each site with a button to copy them.")
    HINT = "Pick a video to open its folder or copy its captions."

    def shown(self):
        self.clear()
        self.title("Videos", "Everything made so far, newest first.")
        v = videos()
        if not v:
            self.text("Nothing yet. Record something on the Record page and it shows up here a few minutes after you "
                      "stop.", 12, DIM)
            return
        canvas = tk.Canvas(self.body, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(self.body, command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=820)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        for folder, p in v:
            c = tk.Frame(inner, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            c.pack(fill="x", pady=4)
            tk.Label(c, text=p["title"], bg=PANEL, fg=FG, font=(FONT, 12, "bold"), anchor="w").pack(fill="x", padx=14,
                                                                                                 pady=(8, 0))
            tk.Label(c, text=f"{p['made']}  ·  {p['kind']}  ·  {round(p['seconds'] / 60)} min  ·  "
                             + (f"{len(p['shorts'])} clip{'' if len(p['shorts']) == 1 else 's'}" if p['shorts'] else "clips still being made"),
                 bg=PANEL, fg=DIM, font=(FONT, 10), anchor="w").pack(
                fill="x", padx=14)
            r = tk.Frame(c, bg=PANEL)
            r.pack(fill="x", padx=10, pady=8)
            self.button(r, "Open folder", lambda f=folder: open_path(f)).pack(side="left", padx=4)
            self.button(r, "Captions", lambda p=p: self.captions(p), primary=False).pack(side="left", padx=4)

    def captions(self, p):
        top = tk.Toplevel(self)
        top.title(f"Captions: {p['title']}")
        top.configure(bg=BG, padx=16, pady=12)
        s = p["shorts"][0] if p["shorts"] else {}
        texts = [("YouTube title", p["youtube"]["title"]), ("YouTube description", p["youtube"]["description"])]
        if s:
            texts += [("Shorts title", s["youtube"]["title"]), ("Shorts description", s["youtube"]["description"]),
                      ("Instagram", s["instagram"]), ("Facebook", s["facebook"])]
        for name, t in texts:
            r = tk.Frame(top, bg=BG)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=name, bg=BG, fg=FG, font=(FONT, 10, "bold"), width=18, anchor="nw").pack(side="left",
                                                                                                anchor="n")
            box = tk.Text(r, height=min(6, t.count("\n") + 2), width=70, font=(FONT, 10), wrap="word")
            box.insert("1.0", t)
            box.pack(side="left")

            def copy(t=t, name=name):
                top.clipboard_clear()
                top.clipboard_append(t)
                self.app.say(f"Copied the {name}.")
            tk.Button(r, text="Copy", command=copy).pack(side="left", padx=6, anchor="n")


# ------------------------------------------------------------------ Posting
class PostingPage(Page):
    HELP = ("Posting (optional)\n\nPosts one clip a day per site through Buffer (free plan: 3 channels).\n\n"
            "1. In Buffer, connect YouTube, Instagram and your Facebook Page, then make an API key (Settings > API).\n"
            "2. Paste the key and the three channel ids here.\n3. Pick hosting: Buffer needs each clip at a public web "
            "address for a moment. Either a folder your web server serves, or a Shopify store's Files.\n"
            "4. Turn posting on. Then press Post what's ready (or let a daily timer do it).\n\nWhile posting is on "
            "hold, nothing is uploaded or scheduled.")
    HINT = "Optional. Nothing is posted while posting is on hold."

    def shown(self):
        self.clear()
        c = config.load()
        self.title("Posting", "Optional: one clip a day on each site, through Buffer. Nothing is posted while this is "
                              "on hold.")
        self.vars = {}
        fields = [("buffer_key", "Buffer API key", c.get("buffer_key", ""), True)]
        for site in ("youtube", "instagram", "facebook"):
            fields.append((f"ch_{site}", f"{site.capitalize()} channel id", c.get("channels", {}).get(site, ""), False))
        h = c.get("hosting", {})
        fields += [("host_folder", "Hosting folder", h.get("folder", ""), False),
                   ("host_url", "…its web address", h.get("base_url", ""), False),
                   ("post_time", "Post at", c.get("post_time", "18:00"), False)]
        for key, label, val, secret in fields:
            r = self.row(pady=3)
            tk.Label(r, text=label, bg=BG, fg=FG, font=(FONT, 11), width=20, anchor="w").pack(side="left")
            v = tk.StringVar(value=val)
            tk.Entry(r, textvariable=v, font=(FONT, 11), relief="solid", bd=1, width=50,
                     show="•" if secret else "").pack(side="left", ipady=3)
            self.vars[key] = v
        self.on = tk.BooleanVar(value=c.get("posting") == "on")
        self.switch = tk.Checkbutton(self.body, text="Posting is ON (untick to put everything on hold)",
                                     variable=self.on, bg=BG, font=(FONT, 11, "bold"))
        self.switch.pack(anchor="w", pady=8)
        r = self.row()
        self.button(r, "Save", self.save).pack(side="left")
        self.button(r, "Check what's been posted", lambda: self.run(["--check"]), primary=False).pack(side="left",
                                                                                                    padx=8)
        self.button(r, "Post what's ready", lambda: self.run([]), primary=False).pack(side="left")
        self.log = self.log_box(8)
        self.run(["--check"] if c.get("buffer_key") else [], quiet_start=True)

    def save(self):
        v = {k: x.get().strip() for k, x in self.vars.items()}
        upd = {"buffer_key": v["buffer_key"], "post_time": v["post_time"] or "18:00",
               "channels": {s: v[f"ch_{s}"] for s in ("youtube", "instagram", "facebook") if v[f"ch_{s}"]},
               "posting": "on" if self.on.get() else "hold"}
        if v["host_folder"] and v["host_url"]:
            upd["hosting"] = {"type": "folder", "folder": v["host_folder"], "base_url": v["host_url"]}
        save_config(upd)
        self.app.say("Saved." + (" Posting is ON." if self.on.get() else " Posting is on hold."))
        self.shown()

    def run(self, args, quiet_start=False):
        if not quiet_start:
            write(self.log, "Asking Buffer…\n")
        Job(self, self.log, lambda log: log(subprocess.run([sys.executable, str(HERE / "post.py")] + args,
                                                           capture_output=True, text=True).stdout or "Nothing to report."))


def tutorial(app):
    pg = app.page
    log = lambda: pg("record").log.get("1.0", "end")
    return [
        {"title": "Welcome to Clip Pipeline", "target": lambda: app.tour_button,
         "text": "One person can't edit a video five ways for five sites every day. Clip Pipeline does that part. You "
                 "record and type the video's name. You get the full video, vertical clips for Shorts and Reels, a "
                 "thumbnail, and the title, description and hashtags for each site.\n\nAbout four minutes.",
         "do": "click Next."},
        {"title": "Start here: the checklist", "page": "start", "target": lambda: pg("start").checklist,
         "text": "Each line is one part of the setup, with a button to fix it if it's missing. You work down it once. "
                 "After that you only use Record and Videos.",
         "do": "read the list, then click Next."},
        {"title": "Your channel", "page": "channel", "target": lambda: pg("channel").fields,
         "text": "Your name goes on every thumbnail and your @handle under every clip. Your links and hashtag go "
                 "into every caption. Type them once here.",
         "do": "type your channel's name (and your @handle if you have one), then click Save.",
         "check": lambda _: config.load()["brand"]["name"] not in ("", "My Channel")},
        {"title": "Three kinds of video", "page": "record", "target": lambda: pg("record").kinds,
         "text": "Gameplay records the screen and the game's sound. Reading is your camera over a banner, with no "
                 "sound. Screen is the screen with a small camera in the corner. Each kind gets its own clips and "
                 "wording. 'Set up OBS' makes all three in OBS for you.",
         "do": "click Next. You'll set up OBS when you're ready to record."},
        {"title": "See it work", "page": "record", "target": lambda: pg("record").sample_btn,
         "text": "This makes a 75-second test video and runs it through the same steps a real recording goes "
                 "through.",
         "do": "click Try it with a sample video.", "start": log,
         "check": lambda old: log().strip() != old.strip()},
        {"title": "Videos", "page": "videos", "target": lambda: pg("videos").body,
         "text": "Everything made so far, newest first. The sample shows up here in a minute or two. Open folder "
                 "shows the full video, the clips and the thumbnail. Captions shows the text for each site, with a "
                 "Copy button.",
         "do": "come back to this page in a couple of minutes to see the sample. Click Next."},
        {"title": "Posting (optional)", "page": "posting", "target": lambda: pg("posting").switch,
         "text": "If you want it, one clip a day goes out on each site through Buffer, a scheduling service with a "
                 "free plan. It stays on hold until you tick this box, so nothing is posted by surprise.",
         "do": "leave it on hold for now. Click Next."},
        {"title": "You're ready", "target": lambda: app.tour_button,
         "text": "Work down Start here once. After that it's: Record, stop, type the name. The rest happens in the "
                 "background.\n\nPress F1 on any page for help with that page.",
         "do": "click Done."},
    ]


def main():
    app = App("Clip Pipeline", "Record once. Post everywhere.", ACCENT, ABOUT, class_name="ClipPipeline")
    app.add_page("start", "Start here", StartPage)
    app.add_page("channel", "My channel", ChannelPage)
    app.add_page("record", "Record", RecordPage)
    app.add_page("videos", "Videos", VideosPage)
    app.add_page("posting", "Posting", PostingPage)
    if (HERE / "icon.png").exists():
        app.iconphoto(True, tk.PhotoImage(file=str(HERE / "icon.png")))
    app.set_tutorial(lambda: tutorial(app), Path(config.CONFIG).parent / "app.json")
    app.run("start")


if __name__ == "__main__":
    main()
