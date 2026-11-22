#!/usr/bin/env bash
# Watches the OBS recording folders. When a recording is finished it asks for its name (the only thing you do),
# then hands it to process.py, which makes the full video, the vertical clips, the thumbnail and every text.
# One folder per kind of video: recordings/gameplay, recordings/reading, recordings/screen
# (a file put straight into recordings/ is handled as a plain video). Runs as clip-watch.service.
# Needs: inotifywait (inotify-tools), ffmpeg/ffprobe, zenity, notify-send (libnotify-bin), flock.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import config; print(config.root())")"
DIR="$ROOT/recordings"
LOG="$ROOT/watch.log"
mkdir -p "$DIR/gameplay" "$DIR/reading" "$DIR/screen" "$ROOT/named" "$ROOT/ready"

# OBS names a recording by its time ("2026-10-23 12-18-19"): that's one nobody has named yet.
STAMP='^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}-[0-9]{2}-[0-9]{2}$'

inotifywait -m -q -e close_write -e moved_to --format '%w%f' "$DIR" "$DIR/gameplay" "$DIR/reading" "$DIR/screen" | while read -r f; do
  case "$f" in *.mp4) ;; *) continue ;; esac
  sleep 2
  [ -f "$f" ] || continue
  secs=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null || echo 0)
  secs=${secs%.*}
  [ "${secs:-0}" -ge 5 ] || continue   # a mis-click, not a video

  kind="$(basename "$(dirname "$f")")"
  case "$kind" in gameplay|reading|screen) ;; *) kind=general ;; esac
  title="$(basename "${f%.*}")"
  if [[ "$title" =~ $STAMP ]]; then
    ask="$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import templates; print(templates.KINDS['$kind'][0])")"
    title="$(zenity --entry --title="Name this video" --text="$ask" --width=560 --timeout=900 2>/dev/null || true)"
    title="$(printf '%s' "$title" | sed 's/^ *//; s/ *$//')"
    if [ -z "$title" ]; then
      echo "$(date -Is) no name given for $f, left in place" >> "$LOG"
      notify-send "Clips: recording not processed" "Rename the file in recordings/$kind/ to its title and it's picked up." 2>/dev/null || true
      continue
    fi
  fi
  # out of the watched folder first, so nothing here fires twice; process.py moves it on into ready/
  held="$ROOT/named/$(date +%s)_$(basename "$f")"
  mv "$f" "$held"
  echo "$(date -Is) processing [$kind] $title" >> "$LOG"
  notify-send "Clips: making the clips" "$title" 2>/dev/null || true
  (  # one recording at a time, in the background: the next name box never waits on this one
    flock 9
    if out=$(python3 "$HERE/process.py" "$held" "$kind" "$title" 2>>"$LOG"); then
      echo "$(date -Is) done $out" >> "$LOG"
      python3 "$HERE/status.py" >>"$LOG" 2>&1 || true
      notify-send "Clips: ready to post" "$title" 2>/dev/null || true
    else
      echo "$(date -Is) FAILED $held" >> "$LOG"
      notify-send "Clips: clips FAILED" "see $LOG" 2>/dev/null || true
    fi
  ) 9>"$ROOT/.process.lock" &
done
