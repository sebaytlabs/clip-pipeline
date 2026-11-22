# Clip Pipeline

Record in OBS, type the video's name, and you're done. The pipeline makes:

- **the full video**, untouched, for YouTube
- **vertical 1080×1920 clips** for YouTube Shorts, Instagram Reels and Facebook Reels: your picture over a blurred copy of itself, with the title on top and your @handle below
- **a thumbnail** with the title on it
- **every title, description, caption and hashtag**, written for each site
- **a status spreadsheet** showing what's ready, what's scheduled, what's posted and what needs you

It can also schedule the clips to post one a day per site through [Buffer](https://buffer.com). That stays off until you turn it on.

Linux (X11). Needs `ffmpeg`, `inotify-tools`, `zenity`, `libnotify-bin`, Python 3 with `pillow` and `openpyxl`, and OBS (Flatpak or package).

## How it flows

```
OBS stops recording
  → watch.sh sees the new file and asks "What's this video called?"
  → process.py: full.mp4 + short_01.mp4 … + thumb.jpg + post.json in <root>/ready/<date>_<kind>_<name>/
  → status.py rebuilds Posting.xlsx
  → post.py (when posting is on): hosts each clip, schedules it in Buffer, checks what went out, cleans up
```

## Kinds of video

A recording dropped in `recordings/<kind>/` is handled as that kind. Each kind gets its own clips and wording.

| Kind | OBS setup | Clips |
|---|---|---|
| `gameplay` | whole screen + desktop sound, no mic | up to 6 clips of 58 s each, spread evenly through the video |
| `reading` | camera over a banner, silent | the whole sitting sped up to ~45 s, plus 45 s in real time |
| `screen` | whole screen + small camera + desktop sound | up to 4 clips of 58 s each |
| anything else | | handled as `general` |

Encoding runs at the lowest priority and waits while OBS is recording, so a game you're recording never stutters.

## Set up

```
git clone https://github.com/sebaytlabs/clip-pipeline ~/clip-pipeline
cd ~/clip-pipeline
mkdir -p ~/.config/clip-pipeline
cp config.example.json ~/.config/clip-pipeline/config.json     # then put your name, handle and links in it
chmod 600 ~/.config/clip-pipeline/config.json

python3 banner/make_banner.py && python3 banner/make_frame.py  # the reading-session banner, with your name
python3 obs/setup_obs.py --encoder x264                        # close OBS first; qsv (Intel) or nvenc (NVIDIA) if you have them
cp systemd/clip-watch.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now clip-watch.service
```

Now **Record Gameplay**, **Record Reading** and **Record Screen** are in your app menu. Each opens OBS on the right setup.

### Make it yours

- **Wording:** all of it lives in `templates.py`, one function per kind. Change it there.
- **Brand details** come from `config.json`: channel name, @handle, YouTube link, site, the one link you want clicked, and your own hashtag.

## Posting (optional)

YouTube's upload API forces videos from unaudited apps to private, and Meta's Reels API needs app review. A scheduler avoids both. Buffer's free plan covers three channels and ten scheduled posts per channel.

To set it up:
1. In Buffer, connect YouTube, Instagram and your Facebook Page, then make an API key (Settings > API).
2. Put the key and the three channel ids in `config.json`.
3. Pick hosting: Buffer fetches each clip from a public address, and the clip is removed again once every site has posted it.
   - `{"type": "folder", "folder": "/var/www/clips", "base_url": "https://you.com/clips"}` if you have a web server, or
   - `{"type": "shopify", ...}` to use a Shopify store's Files. This needs a custom app with only `read_files` and `write_files`.
4. Set `"posting": "on"`, then run `python3 post.py` once a day (a cron job or a systemd timer).

`python3 post.py --check` only refreshes the status of what's already scheduled. Upload the full video to YouTube yourself; Buffer only takes short videos.

## Tests

```
python3 -m unittest discover tests
python3 templates.py          # prints every kind's texts so you can read them
```

## License

MIT. Made by [Sebayt Labs](https://sebaytlabs.com).
