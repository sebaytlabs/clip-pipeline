"""The title, description and captions for each kind of video. One place to change the wording.

  texts(kind, name) -> {"title", "youtube": {...}, "short": {...}, "instagram": str, "facebook": str, "overlay"}

Written for search and for the first two lines people see: what it is, said plainly, with the words someone
would type to find it; then one link to subscribe and one to your site. Hashtags: your own tag plus a few that
say what the video is (YouTube shows the first three above the title).

Your channel name, links and tag come from config.json ("brand"). Edit the wording below to sound like you.
"""
import re

import config

KINDS = {  # kind: (what the name box asks, YouTube category id)
    "gameplay": ("Game and what this video shows, like:  Stardew Valley: First week walkthrough", "20"),   # Gaming
    "reading": ("The book you read, like:  Atomic Habits", "27"),                                            # Education
    "screen": ("What this video shows, like:  Budget spreadsheet in 5 minutes", "28"),                       # Science & Technology
    "general": ("What's this video called?", "22"),                                                          # People & Blogs
}


def tag(text):
    """'Stardew Valley' -> 'StardewValley': a hashtag from a name."""
    words = re.findall(r"[A-Za-z0-9]+", text.replace("'", "").replace("’", ""))
    return "".join(w[:1].upper() + w[1:] for w in words)[:40]


def clip(text, n):
    """At most n characters, cut at a word."""
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n - 1].rsplit(" ", 1)[0].rstrip(" ,:;-|") + "…"


def links(b):
    """The subscribe and site lines, leaving out any link that isn't set."""
    out = []
    if b["channel"]:
        out.append(f"Subscribe: {b['channel'].rstrip('/')}?sub_confirmation=1")
    if b["link"]:
        out.append(f"More: {b['link']}")
    elif b["site"]:
        out.append(f"More from {b['name']}: {b['site']}")
    return "\n".join(out)


def where_full(b):
    return b["channel"] or "my channel"


def gameplay(name, b):
    game, _, topic = (p.strip() for p in name.partition(":"))
    topic = topic or "Gameplay"
    g, me = tag(game) or "Gaming", b["hashtag"]
    return {
        "title": f"{game}: {topic}",
        "youtube": {
            "title": clip(f"{game}: {topic} | No Commentary Gameplay", 100),
            "description": (
                f"{game}: {topic}. Pure gameplay with no commentary and nothing cut, so you can see exactly how "
                "it's done and follow along at your own pace.\n\n"
                f"{links(b)}\n\n"
                f"- Game: {game}\n- What you'll see: {topic}\n- Format: full gameplay, no talking, no edits\n\n"
                f"#{g} #NoCommentary #Gameplay"),
            "tags": [game, f"{game} gameplay", f"{game} tutorial", f"{game} walkthrough", "no commentary", topic],
        },
        "short": {
            "title": clip(f"{game}: {topic}", 90) + " #shorts",
            "description": f"{topic} in {game}. No commentary. Full video on the channel.\n\n#{g} #NoCommentary #Shorts",
        },
        "instagram": f"{game}: {topic}\n\nPure gameplay, no talking. The full video is on YouTube {b['handle']} "
                     f"(link in bio).\n\n#{g.lower()} #nocommentary #gameplay #{me}",
        "facebook": f"{game}: {topic}\n\nPure gameplay, no talking. Full video: {where_full(b)}\n\n#{g} #Gameplay #{me}",
        "overlay": f"{game}: {topic}",
    }


def reading(name, b):
    book = name.strip()
    t, me = tag(re.split(r"\s+by\s+", book, flags=re.I)[0]) or "Books", b["hashtag"]
    return {
        "title": f"Reading {book}",
        "youtube": {
            "title": clip(f"Reading {book} | Silent Real-Time Reading Session", 100),
            "description": (
                f"A silent, real-time reading session with {book}. No talking and no music: one sitting from "
                "start to finish, so you can read along with your own book or keep it on while you study.\n\n"
                f"{links(b)}\n\n"
                f"- Book: {book}\n- Format: over the shoulder, one sitting, nothing cut\n\n"
                f"#ReadWithMe #StudyWithMe #{t}"),
            "tags": [book, f"{book} reading", "read with me", "study with me", "silent reading", "reading session"],
        },
        "short": {
            "title": clip(f"Reading {book} in under a minute", 90) + " #shorts",
            "description": f"One whole reading session with {book}, sped up. The full silent session is on the channel."
                           f"\n\n#ReadWithMe #StudyWithMe #Shorts",
        },
        "instagram": f"One sitting with {book}, sped up.\n\nThe full silent session is on YouTube {b['handle']} "
                     f"(link in bio).\n\n#readwithme #studywithme #reading #{t.lower()} #{me}",
        "facebook": f"One sitting with {book}, sped up. The full session: {where_full(b)}\n\n#ReadWithMe #{me}",
        "overlay": f"Reading {book}",
    }


def screen(name, b):
    topic, me = name.strip(), b["hashtag"]
    return {
        "title": topic,
        "youtube": {
            "title": clip(topic, 100),
            "description": f"{topic}, shown start to finish on screen, in real time.\n\n{links(b)}\n\n#{tag(topic)[:30]} #{me}",
            "tags": [topic, "tutorial", "how to", "screen recording", b["name"]],
        },
        "short": {"title": clip(topic, 90) + " #shorts", "description": f"{topic}. Full video on the channel.\n\n#{me} #Shorts"},
        "instagram": f"{topic}\n\nFull video on YouTube {b['handle']} (link in bio).\n\n#{me}",
        "facebook": f"{topic}\n\nFull video: {where_full(b)}\n\n#{me}",
        "overlay": topic,
    }


def general(name, b):
    t, me = name.strip(), b["hashtag"]
    return {
        "title": t,
        "youtube": {"title": clip(t, 100), "description": f"{t}\n\n{links(b)}\n\n#{me}", "tags": [t, b["name"]]},
        "short": {"title": clip(t, 90) + " #shorts", "description": f"{t}\n\n#{me} #Shorts"},
        "instagram": f"{t}\n\nLink in bio.\n\n#{me}",
        "facebook": f"{t}\n\n{b['site'] or where_full(b)}\n\n#{me}",
        "overlay": t,
    }


def texts(kind, name, brand=None):
    b = brand or config.load()["brand"]
    out = {"gameplay": gameplay, "reading": reading, "screen": screen}.get(kind, general)(name, b)
    out["kind"], out["category"] = kind, KINDS.get(kind, KINDS["general"])[1]
    return out


if __name__ == "__main__":  # python3 templates.py: a look at each
    for k, n in (("gameplay", "Stardew Valley: First week walkthrough"), ("reading", "Atomic Habits by James Clear"),
                 ("screen", "Budget spreadsheet in 5 minutes"), ("general", "Hello")):
        t = texts(k, n)
        print(f"=== {k}\n{t['youtube']['title']}\n\n{t['youtube']['description']}\n\n[short] {t['short']['title']}\n")
