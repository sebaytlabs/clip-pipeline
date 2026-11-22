"""Settings for the whole pipeline, in one file you own: ~/.config/clip-pipeline/config.json

Everything here has a default, so the pipeline runs before you set anything. A full example is in
config.example.json. Keys and passwords live only in that file (make it readable by you alone: chmod 600).
"""
import json
import os

CONFIG = os.path.expanduser(os.environ.get("CLIP_PIPELINE_CONFIG", "~/.config/clip-pipeline/config.json"))

DEFAULTS = {
    "root": "~/Videos/Clips",            # recordings/, named/, ready/ and the status sheet live here
    "brand": {
        "name": "My Channel",            # printed on thumbnails
        "handle": "@mychannel",          # printed under every vertical clip
        "channel": "",                   # https://www.youtube.com/@mychannel
        "site": "",                      # https://example.com
        "link": "",                      # the one thing you want people to click (a product, a newsletter); optional
        "hashtag": "mychannel",          # your own tag, added to every post
    },
    "posting": "hold",                   # "hold": nothing is uploaded or scheduled. "on": post.py schedules.
    "post_time": "18:00",
    "ahead_days": 7,
    "buffer_key": "",
    "channels": {},                      # Buffer channel ids: {"youtube": "...", "instagram": "...", "facebook": "..."}
    "hosting": {},                       # where clips sit while Buffer fetches them; see README
}


def load():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            user = json.load(f)
    except (OSError, ValueError):
        user = {}
    c = {**DEFAULTS, **user}
    c["brand"] = {**DEFAULTS["brand"], **user.get("brand", {})}
    c["root"] = os.path.expanduser(c["root"])
    return c


def root():
    return load()["root"]
