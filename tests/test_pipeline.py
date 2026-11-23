"""python3 -m unittest discover tests   (no video work, no network)"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

T = tempfile.mkdtemp()
Path(T, "c.json").write_text(json.dumps({"root": T, "brand": {"name": "Test", "handle": "@t", "hashtag": "tt",
                                                               "channel": "https://youtube.com/@t"}}))
os.environ["CLIP_PIPELINE_CONFIG"] = str(Path(T, "c.json"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import post  # noqa: E402
import process  # noqa: E402
import templates  # noqa: E402


class Templates(unittest.TestCase):
    def test_every_kind_fits_limits(self):
        for kind in ("gameplay", "reading", "screen", "general", "unknown"):
            t = templates.texts(kind, "A very long name " * 10)
            self.assertLessEqual(len(t["youtube"]["title"]), 100)
            self.assertLessEqual(len(t["short"]["title"]), 100)
            self.assertIn("#tt", t["instagram"])

    def test_tag_and_clip(self):
        self.assertEqual(templates.tag("Baldur's Gate 3"), "BaldursGate3")
        self.assertTrue(templates.clip("a " * 80, 20).endswith("…"))

    def test_links_skip_empty(self):
        d = templates.texts("general", "Hi")["youtube"]["description"]
        self.assertIn("sub_confirmation=1", d)
        self.assertNotIn("More from", d)


class Process(unittest.TestCase):
    def test_clip_starts_spread_and_in_range(self):
        s = process.starts(1200, "gameplay")
        self.assertEqual(len(s), 6)
        self.assertTrue(all(0 <= x <= 1200 - process.CLIP_S for x in s))
        self.assertEqual(process.starts(40, "gameplay"), [0.0])

    def test_vertical_filter_fits_any_size(self):
        hd = process.vertical_filter("gameplay", "/tmp/t.txt", 1)
        self.assertIn("y=1402", hd)  # 16:9: picture 608 high, handle 46 below it
        self.assertNotIn("1440:1080", process.vertical_filter("reading", "/tmp/t.txt", 1, dims=(1280, 720)))
        tall = process.vertical_filter("gameplay", "/tmp/t.txt", 2, dims=(1080, 1920))
        self.assertIn("y=1830", tall)  # a vertical video fills the frame: the handle stays on screen

    def test_safe_name(self):
        self.assertEqual(process.safe('a/b:c*"d'), "a b c d")


class Hosting(unittest.TestCase):
    def test_folder_upload_and_delete(self):
        src = Path(T, "clip.mp4")
        src.write_bytes(b"x")
        web = Path(T, "web")
        web.mkdir()
        h = post.Folder({"folder": str(web), "base_url": "https://e.com/c/"})
        name, url = h.upload(str(src), "alt")
        self.assertTrue((web / name).exists())
        self.assertTrue(url.startswith("https://e.com/c/") and url.endswith("clip.mp4"))
        h.delete(name)
        self.assertFalse((web / name).exists())

    def test_hold_by_default(self):
        self.assertEqual(config.load()["posting"], "hold")


if __name__ == "__main__":
    unittest.main()
