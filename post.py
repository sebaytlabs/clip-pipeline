#!/usr/bin/env python3
"""Posting, without you: the clips go to YouTube Shorts, Instagram Reels and Facebook Reels through Buffer's API,
one a day per site at the same time each day. The status sheet (status.py) says where everything stands.

Set up in ~/.config/clip-pipeline/config.json (chmod 600; see config.example.json):
  buffer_key   a Buffer personal API key (Buffer > Settings > API). Scopes: account:read, posts:read, posts:write.
  channels     Buffer channel ids for youtube, instagram, facebook.
  hosting      where each clip sits at a public address while Buffer fetches it. It's removed once every site
               has posted it. Two kinds:
                 {"type": "folder", "folder": "/path/served/by/your/web/server", "base_url": "https://you.com/clips"}
                 {"type": "shopify", "shop": "store.myshopify.com", "client_id": "...", "client_secret": "..."}
                   (a custom app with read_files and write_files only; clips go in the store's Files)
  posting      "hold" (default) or "on". While it's "hold" NOTHING is uploaded or scheduled.
  post_time    "18:00" local time; ahead_days 7 (Buffer's free plan allows 10 scheduled posts per channel).

  python3 post.py            say what's missing; if posting is on, schedule what's ready and check what was sent
  python3 post.py --check    only refresh the status of posts already scheduled (safe while on hold)
The full video (full.mp4) is not posted here: Buffer only takes short videos for YouTube. Upload it yourself.
"""
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request
import shutil
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as settings  # noqa: E402

READY = os.path.join(settings.root(), "ready")
SITES = ("youtube", "instagram", "facebook")
SHOPIFY_API = "2025-10"
BUFFER = "https://api.buffer.com"


def config():
    return settings.load()


def missing_setup():
    """[(what, what to do)] for each thing posting still needs; empty once it can run."""
    c = config()
    out = []
    if not c.get("buffer_key"):
        out.append(("Posting is not switched on: no Buffer API key yet",
                    "In Buffer: Settings > API > New key. Put it in config.json as buffer_key."))
    if not c.get("hosting"):
        out.append(("Posting is not switched on: no place to host clips for Buffer",
                    "Set hosting in config.json: a folder your web server serves, or Shopify Files."))
    for site in SITES:
        if c.get("buffer_key") and not (c.get("channels") or {}).get(site):
            out.append((f"Buffer has no {site} channel connected", "Connect it in Buffer > Channels."))
    if not out and c.get("posting", "hold") != "on":
        out.append(("Posting is on hold",
                    'When you want clips to start going out, set "posting": "on" in config.json.'))
    return out


# ---------- web calls ----------

def call(url, body, headers, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
                                                                                "User-Agent": "clip-pipeline", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def buffer(c, query, variables=None):
    r = call(BUFFER, {"query": query, "variables": variables or {}}, {"Authorization": "Bearer " + c["buffer_key"]})
    if r.get("errors"):
        raise RuntimeError("; ".join(e.get("message", "?") for e in r["errors"]))
    return r["data"]


class Shopify:
    def __init__(self, h):
        self.h = h
        t = call(f"https://{h['shop']}/admin/oauth/access_token",
                 {"client_id": h["client_id"], "client_secret": h["client_secret"], "grant_type": "client_credentials"}, {})
        self.token = t["access_token"]

    def gql(self, query, variables=None):
        r = call(f"https://{self.h['shop']}/admin/api/{SHOPIFY_API}/graphql.json", {"query": query, "variables": variables or {}},
                 {"X-Shopify-Access-Token": self.token})
        if r.get("errors"):
            raise RuntimeError(str(r["errors"])[:300])
        return r["data"]

    def upload(self, path, alt):
        """Put a video in the store's Files; return (file id, public mp4 address)."""
        size = os.path.getsize(path)
        d = self.gql("""mutation($i: [StagedUploadInput!]!) { stagedUploadsCreate(input: $i) {
              stagedTargets { url resourceUrl parameters { name value } } userErrors { message } } }""",
                     {"i": [{"filename": os.path.basename(path), "mimeType": "video/mp4", "resource": "VIDEO",
                             "fileSize": str(size), "httpMethod": "POST"}]})["stagedUploadsCreate"]
        if d["userErrors"]:
            raise RuntimeError(d["userErrors"][0]["message"])
        t = d["stagedTargets"][0]
        multipart_post(t["url"], [(p["name"], p["value"]) for p in t["parameters"]], path)
        d = self.gql("""mutation($f: [FileCreateInput!]!) { fileCreate(files: $f) { files { id } userErrors { message } } }""",
                     {"f": [{"originalSource": t["resourceUrl"], "contentType": "VIDEO", "alt": alt[:500]}]})["fileCreate"]
        if d["userErrors"]:
            raise RuntimeError(d["userErrors"][0]["message"])
        fid = d["files"][0]["id"]
        for _ in range(60):  # Shopify processes the video before it has a public address (usually under a minute)
            n = self.gql("""query($id: ID!) { node(id: $id) { ... on Video { fileStatus
                  fileErrors { message } sources { url mimeType height } } } }""", {"id": fid})["node"]
            if n and n["fileStatus"] == "READY":
                mp4 = sorted((s for s in n["sources"] if s["mimeType"] == "video/mp4"), key=lambda s: s["height"] or 0)
                return fid, mp4[-1]["url"]
            if n and n["fileStatus"] == "FAILED":
                raise RuntimeError("Shopify could not process the video: " + "; ".join(e["message"] for e in n["fileErrors"]))
            time.sleep(10)
        raise RuntimeError("Shopify took over 10 minutes to process the video")

    def delete(self, fid):
        self.gql("mutation($ids: [ID!]!) { fileDelete(fileIds: $ids) { deletedFileIds userErrors { message } } }", {"ids": [fid]})


class Folder:
    """Hosting on your own web server: the clip is copied into a folder it serves."""
    def __init__(self, h):
        self.folder, self.base = h["folder"], h["base_url"].rstrip("/")

    def upload(self, path, alt):
        name = f"{uuid.uuid4().hex[:12]}-{os.path.basename(path)}"
        shutil.copyfile(path, os.path.join(self.folder, name))
        return name, f"{self.base}/{urllib.request.quote(name)}"

    def delete(self, name):
        try:
            os.remove(os.path.join(self.folder, name))
        except FileNotFoundError:
            pass


def host(c):
    h = c["hosting"]
    return Folder(h) if h.get("type") == "folder" else Shopify(h)


def multipart_post(url, fields, path):
    b = uuid.uuid4().hex
    head = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields)
    head += (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
             f"Content-Type: video/mp4\r\n\r\n").encode()
    with open(path, "rb") as f:
        body = head + f.read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=600) as r:
        if r.status >= 300:
            raise RuntimeError(f"upload refused: HTTP {r.status}")


# ---------- scheduling ----------

ERRORS = "".join(f" ... on {t} {{ message }}" for t in ("NotFoundError", "UnauthorizedError", "UnexpectedError",
                                                          "RestProxyError", "LimitReachedError", "InvalidInputError"))


def create(c, site, url, piece, due):
    meta = {"youtube": {"youtube": {"title": piece["youtube"]["title"][:100], "privacy": "public", "categoryId": piece.get("category", "22"),
                                    "madeForKids": False, "notifySubscribers": True}},
            "instagram": {"instagram": {"type": "reel", "shouldShareToFeed": True}},
            "facebook": {"facebook": {"type": "reel"}}}[site]
    text = {"youtube": piece["youtube"]["description"], "instagram": piece["instagram"], "facebook": piece["facebook"]}[site]
    d = buffer(c, "mutation($i: CreatePostInput!) { createPost(input: $i) { __typename ... on PostActionSuccess { post { id dueAt } }"
               + ERRORS + " } }",
               {"i": {"channelId": c["channels"][site], "text": text, "schedulingType": "automatic", "mode": "customScheduled",
                      "dueAt": due.astimezone().isoformat(), "needsApproval": False, "metadata": meta,
                      "assets": [{"video": {"url": url, "metadata": {"title": piece["youtube"]["title"][:100]}}}]}})["createPost"]
    if d["__typename"] != "PostActionSuccess":
        raise RuntimeError(d.get("message") or d["__typename"])
    return d["post"]


def pieces():
    for path in sorted(glob.glob(os.path.join(READY, "*", "post.json"))):
        with open(path, encoding="utf-8") as f:
            yield os.path.dirname(path), json.load(f)


def save(folder, post):
    tmp = os.path.join(folder, ".post.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(post, f, indent=1, ensure_ascii=False)
    os.replace(tmp, os.path.join(folder, "post.json"))


def word(st):
    return st if isinstance(st, str) else st.get("state", "ready")


def check(c, shop=None):
    """Ask Buffer what happened to everything scheduled; mark posted/failed; remove hosted clips nobody needs any more."""
    for folder, p in pieces():
        changed = False
        for s in p["shorts"]:
            for site, st in s["status"].items():
                if word(st) != "scheduled":
                    continue
                n = buffer(c, "query($i: PostInput!) { post(input: $i) { status sentAt error { message } } }",
                           {"i": {"id": st["buffer_id"]}})["post"]
                if n["status"] == "sent":
                    s["status"][site] = {"state": "posted", "when": n["sentAt"], "buffer_id": st["buffer_id"]}
                elif n["status"] == "error":
                    s["status"][site] = {**st, "state": "failed", "why": (n.get("error") or {}).get("message", "Buffer reported an error")}
                else:
                    continue
                changed = True
            if s.get("hosted_file") and all(word(x) in ("posted", "failed") for x in s["status"].values()):
                shop = shop or host(c)
                shop.delete(s["hosted_file"])
                s.pop("hosted_file")
                s.pop("hosted_url", None)
                changed = True
        if changed:
            save(folder, p)
    return shop


def taken(c):
    """The dates (per site) that already have something scheduled, so each site gets one clip a day."""
    days = {site: set() for site in SITES}
    for _, p in pieces():
        for s in p["shorts"]:
            for site, st in s["status"].items():
                if word(st) == "scheduled" and st.get("when"):
                    days[site].add(datetime.fromisoformat(st["when"].replace("Z", "+00:00")).astimezone().date())
    return days


def schedule(c):
    hh, mm = map(int, c.get("post_time", "18:00").split(":"))
    ahead = int(c.get("ahead_days", 7))
    now = datetime.now().astimezone()
    days = taken(c)
    shop = None
    out = []
    for folder, p in pieces():
        for s in p["shorts"]:
            for site in SITES:
                if word(s["status"].get(site, "ready")) != "ready":
                    continue
                day = next((now.date() + timedelta(days=i) for i in range(ahead + 1)
                            if now.date() + timedelta(days=i) not in days[site]
                            and datetime.combine(now.date() + timedelta(days=i), datetime.min.time()).astimezone().replace(hour=hh, minute=mm) > now + timedelta(minutes=30)), None)
                if day is None:
                    continue  # this site's week is full; next run picks it up
                due = datetime.combine(day, datetime.min.time()).astimezone().replace(hour=hh, minute=mm)
                try:
                    if not s.get("hosted_url"):
                        shop = shop or host(c)
                        s["hosted_file"], s["hosted_url"] = shop.upload(os.path.join(folder, s["file"]), f"{p['title']} {s['file']}")
                        save(folder, p)
                    piece = {"youtube": s["youtube"], "instagram": s["instagram"], "facebook": s["facebook"],
                             "category": p["youtube"].get("category", "22")}
                    post = create(c, site, s["hosted_url"], piece, due)
                    s["status"][site] = {"state": "scheduled", "when": post["dueAt"], "buffer_id": post["id"]}
                    days[site].add(day)
                    out.append(f"{site}: {p['title']} {s['file']} on {due:%a %b %-d %-I:%M %p}")
                except (RuntimeError, urllib.error.URLError, OSError, KeyError) as e:
                    s["status"][site] = {"state": "failed", "why": str(e)[:300]}
                    out.append(f"{site}: {p['title']} {s['file']} FAILED: {e}")
                save(folder, p)
    return out


if __name__ == "__main__":
    missing = missing_setup()
    c = config()
    on = c.get("posting", "hold") == "on"
    for what, how in missing:
        print(f"- {what}\n  {how}")
    if c.get("buffer_key") and (on or "--check" in sys.argv):
        check(c)
    if on and not [m for m in missing if "on hold" not in m[0]]:
        for line in schedule(c):
            print(line)
    try:
        import status
        status.build(missing)
    except ImportError:
        print("(The status spreadsheet needs openpyxl: pip install openpyxl. Everything else still works.)")
    except Exception as e:  # the spreadsheet is a convenience; never let it stop posting
        print("(spreadsheet not rebuilt:", e, ")")
