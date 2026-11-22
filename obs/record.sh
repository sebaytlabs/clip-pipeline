#!/usr/bin/env bash
# One click: OBS opens on the right setup for the kind of video, ready to record.
# Usage: record.sh gameplay | reading | screen   (anything after it goes to OBS, e.g. --startrecording)
# When you stop recording, a box asks for the video's name; everything after that is automatic.
set -u
kind="${1:-}"
shift 2>/dev/null || true
case "$kind" in
  gameplay) name="Gameplay";        scene="Game" ;;
  reading)  name="Reading Session"; scene="Reading" ;;
  screen)   name="Screen";          scene="Screen" ;;
  *) echo "usage: record.sh gameplay|reading|screen" >&2; exit 2 ;;
esac

if pgrep -x obs >/dev/null; then  # one OBS at a time: bring it forward instead of opening a second
  notify-send "OBS is already open" "Close it first to switch to $name." 2>/dev/null
  wmctrl -x -a obs 2>/dev/null
  exit 0
fi

if flatpak info com.obsproject.Studio >/dev/null 2>&1; then
  obs=(flatpak run com.obsproject.Studio)
else
  obs=(obs)
fi
exec "${obs[@]}" --disable-shutdown-check --profile "$name" --collection "$name" --scene "$scene" "$@"
