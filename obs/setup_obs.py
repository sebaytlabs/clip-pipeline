#!/usr/bin/env python3
"""Writes three ready-to-record OBS setups (profile + scene collection + menu launcher). Re-runnable; close OBS
first (it rewrites its files when it quits). Linux, X11. Works with OBS from Flatpak or from your package manager.

  Gameplay   the whole screen + desktop sound, no camera, no mic       -> <root>/recordings/gameplay
  Reading    the camera over a banner, silent                          -> <root>/recordings/reading
  Screen     the whole screen + a small camera + desktop sound         -> <root>/recordings/screen

All record 1080p30 to hybrid MP4 (safe if OBS crashes) and name files by time, so the watcher asks for a title.

  python3 setup_obs.py [--camera /dev/video0] [--encoder x264|qsv|nvenc]

Encoder: x264 works everywhere; qsv (Intel) or nvenc (NVIDIA) take the work off the processor,
which matters when you record a game. A cheap webcam that stops after 0 frames: keep it on YUYV (the default here).
"""
import configparser
import hashlib
import json
import os
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
FLATPAK = os.path.join(HOME, ".var/app/com.obsproject.Studio/config/obs-studio")
OBS = FLATPAK if os.path.isdir(FLATPAK) else os.path.join(HOME, ".config/obs-studio")
REC = os.path.join(config.root(), "recordings")
W, H = 1920, 1080
ENCODER = "x264"
MAIN_CANVAS = "6c69626f-6273-4c00-9d88-c5136d61696e"  # OBS's own id for the main canvas
CAMERA = {"device_id": "/dev/video0", "res_type": 1, "frame_interval": 333333,  # YUYV 640x480 30 fps: the mode
          "pixelformat": 1448695129, "resolution": 41943520}                     # every webcam has

SETUPS = {  # key: (profile/collection name, scene name, launcher label, quality, what the launcher says)
    "gameplay": ("Gameplay", "Game", "Record Gameplay", "HQ", "Whole screen and game sound. No camera, no mic."),
    "reading": ("Reading Session", "Reading", "Record Reading", "Small", "The camera, framed. Silent."),
    "screen": ("Screen", "Screen", "Record Screen", "Small", "The whole screen with a small camera."),
}


def source(name, kind, settings, mixers=0, hotkeys=None):
    return {"prev_ver": 553648128, "name": name, "uuid": str(uuid.uuid4()), "id": kind, "versioned_id": kind,
            "settings": settings, "mixers": mixers, "sync": 0, "flags": 0, "volume": 1.0, "balance": 0.5,
            "enabled": True, "muted": False, "push-to-mute": False, "push-to-mute-delay": 0, "push-to-talk": False,
            "push-to-talk-delay": 0, "hotkeys": hotkeys or {}, "deinterlace_mode": 0, "deinterlace_field_order": 0,
            "monitoring_type": 0, "monitoring_enabled": False, "private_settings": {}}


def item(src, n, x, y, w, h):
    """A source placed in a box (x, y, w, h): scaled to fit inside it, centred. OBS reads the *_rel values
    (half the canvas height is 1.0) and rewrites the pixel ones from them."""
    return {"name": src["name"], "source_uuid": src["uuid"], "visible": True, "locked": True, "rot": 0.0,
            "scale_ref": {"x": float(W), "y": float(H)}, "align": 5, "bounds_type": 2, "bounds_align": 0,
            "bounds_crop": False, "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0, "id": n,
            "group_item_backup": False, "pos": {"x": float(x), "y": float(y)},
            "pos_rel": {"x": (x - W / 2) / (H / 2), "y": (y - H / 2) / (H / 2)},
            "scale": {"x": 1.0, "y": 1.0}, "scale_rel": {"x": 1.0, "y": 1.0},
            "bounds": {"x": float(w), "y": float(h)}, "bounds_rel": {"x": w / (H / 2), "y": h / (H / 2)},
            "scale_filter": "bicubic", "blend_method": "default", "blend_type": "normal",
            "show_transition": {"duration": 0}, "hide_transition": {"duration": 0}, "private_settings": {}}


def scene(name, items):
    s = source(name, "scene", {"custom_size": False, "id_counter": len(items), "items": items},
               hotkeys={"OBSBasic.SelectScene": []})
    s["canvas_uuid"] = MAIN_CANVAS
    return s


def collection(name, scene_name, sources, items, desktop_audio):
    data = {"name": name, "sources": sources + [scene(scene_name, items)], "groups": [],
            "scene_order": [{"name": scene_name}], "current_scene": scene_name, "current_program_scene": scene_name,
            "canvases": [], "current_transition": "Fade", "transition_duration": 300, "transitions": [],
            "quick_transitions": [], "saved_projectors": [], "preview_locked": False, "scaling_enabled": True,
            "scaling_level": -12, "scaling_off_x": 0.0, "scaling_off_y": 0.0, "virtual-camera": {"type2": 3},
            "modules": {}, "resolution": {"x": W, "y": H}, "migration_resolution": {"x": W, "y": H}, "version": 2}
    if desktop_audio:  # what the computer plays (the game, a video); never a microphone
        data["DesktopAudioDevice1"] = source("Desktop Audio", "pulse_output_capture", {"device_id": "default"}, mixers=255,
                                             hotkeys={"libobs.mute": [], "libobs.unmute": []})
    return data


def collections():
    screen = source("Screen", "xshm_input", {"screen": 0, "show_cursor": True, "advanced": False})
    frame = source("Reading frame", "image_source", {"file": os.path.join(HERE, "..", "banner", "reading-frame.png")})
    frame["settings"]["file"] = os.path.normpath(frame["settings"]["file"])
    cam_r, cam_s = source("Camera", "v4l2_input", dict(CAMERA)), source("Camera", "v4l2_input", dict(CAMERA))
    screen2 = source("Display", "xshm_input", {"screen": 0, "show_cursor": True, "advanced": False})
    return {
        "gameplay": collection("Gameplay", "Game", [screen], [item(screen, 1, 0, 0, W, H)], True),
        "reading": collection("Reading Session", "Reading", [frame, cam_r],
                              [item(frame, 1, 0, 0, W, H), item(cam_r, 2, 240, 0, 1440, H)], False),
        "screen": collection("Screen", "Screen", [screen2, cam_s],
                             [item(screen2, 1, 0, 0, W, H), item(cam_s, 2, 1580, 820, 320, 240)], True),
    }


def profile_ini(name, folder, quality):
    c = configparser.RawConfigParser()
    c.optionxform = str
    c["General"] = {"Name": name}
    c["Video"] = {"BaseCX": W, "BaseCY": H, "OutputCX": W, "OutputCY": H, "FPSType": 0, "FPSCommon": 30, "FPSInt": 30,
                  "FPSNum": 30, "FPSDen": 1, "ScaleType": "bicubic", "ColorFormat": "NV12", "ColorSpace": "709",
                  "ColorRange": "Partial"}
    c["Output"] = {"Mode": "Simple", "FilenameFormatting": "%CCYY-%MM-%DD %hh-%mm-%ss"}  # a timestamp: the watcher asks for the name
    c["SimpleOutput"] = {"FilePath": folder, "RecFormat2": "hybrid_mp4", "RecQuality": quality, "RecEncoder": ENCODER,
                         "VBitrate": 6000, "ABitrate": 160, "UseAdvanced": "false", "Preset": "veryfast",
                         "RecRB": "false", "RecTracks": 1, "StreamAudioEncoder": "aac", "RecAudioEncoder": "aac"}
    c["Audio"] = {"SampleRate": 48000, "ChannelSetup": "Stereo"}
    return c


def write_launcher(key, label, comment):
    text = ("[Desktop Entry]\nType=Application\n"
            f"Name={label}\nComment={comment}\n"
            f"Exec={os.path.join(HERE, 'record.sh')} {key}\n"
            "Icon=com.obsproject.Studio\nTerminal=false\nCategories=AudioVideo;Recorder;\n")
    for folder in (os.path.join(HOME, ".local/share/applications"), os.path.join(HOME, "Desktop")):
        path = os.path.join(folder, f"clip-record-{key}.desktop")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(path, 0o755)
        if folder.endswith("Desktop"):  # Xfce only runs a desktop launcher it trusts: its checksum says it's ours
            digest = hashlib.sha256(text.encode()).hexdigest()
            subprocess.run(["gio", "set", path, "metadata::trusted", "true"], capture_output=True)
            subprocess.run(["gio", "set", "-t", "string", path, "metadata::xfce-exe-checksum", digest], capture_output=True)


def main():
    global ENCODER
    args = sys.argv[1:]
    if "--camera" in args:
        CAMERA["device_id"] = args[args.index("--camera") + 1]
    if "--encoder" in args:
        ENCODER = {"x264": "x264", "qsv": "qsv", "nvenc": "nvenc"}[args[args.index("--encoder") + 1]]
    if subprocess.run(["pgrep", "-x", "obs"], capture_output=True).returncode == 0:
        raise SystemExit("Close OBS first: it overwrites these files when it quits.")
    made = collections()
    for key, (name, scene_name, label, quality, comment) in SETUPS.items():
        folder = os.path.join(REC, key)
        os.makedirs(folder, exist_ok=True)
        pdir = os.path.join(OBS, "basic/profiles", name)
        os.makedirs(pdir, exist_ok=True)
        with open(os.path.join(pdir, "basic.ini"), "w", encoding="utf-8") as f:
            profile_ini(name, folder, quality).write(f, space_around_delimiters=False)
        with open(os.path.join(OBS, "basic/scenes", name + ".json"), "w", encoding="utf-8") as f:
            json.dump(made[key], f, indent=1)
        write_launcher(key, label, comment)
        print(f"{label}: profile and scenes '{name}', recordings in {folder}")


if __name__ == "__main__":
    main()
