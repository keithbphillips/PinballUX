#!/bin/bash
# PinballUX launcher for the Raspberry Pi 5 cabinet.
#
# Runs the PyQt6 frontend inside the existing rpd-labwc desktop session.
# Key Pi-specific environment:
#   QT_QPA_PLATFORM=xcb            -> run under XWayland (Qt wayland plugin not
#                                     installed; XWayland presents both monitors
#                                     as one X screen so absolute positioning works)
#   QT_FFMPEG_DECODING_HW_DEVICE_TYPES=""
#                                  -> force SOFTWARE video decode. The Pi 5 has no
#                                     H.264 hardware decoder; Qt's FFmpeg backend
#                                     otherwise tries h264_v4l2m2m, fails, and hangs
#                                     the wheel on table preview videos.
# Table launches go through vpinball.sh (set as vpx.executable_path in
# ~/.config/pinballux/config.json), which clears the texture cache and sets the
# native-Wayland env VPinball needs.

cd "$(dirname "$(readlink -f "$0")")" || exit 1

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export QT_QPA_PLATFORM=xcb
export QT_FFMPEG_DECODING_HW_DEVICE_TYPES=""

# Hide the mouse cursor across ALL X11 windows for the whole session. Qt's
# setOverrideCursor in main.py only blanks the cursor inside PinballUX's own
# windows; when VPX (a separate XWayland/SDL client) maps its table window the
# X11 cursor reappears over it. unclutter-xfixes uses XFixes to hide the cursor
# on the X display itself, so it covers VPX too. --idle 0 hides immediately,
# --start-hidden hides before any pointer motion. Start one per session only.
if ! pgrep -x unclutter >/dev/null 2>&1; then
    unclutter --idle 0 --start-hidden >/dev/null 2>&1 &
fi

# Defensive: free a stale single-instance lock left by a previous hard kill/crash.
# attach()+detach() removes the QSharedMemory segment only if no live instance
# still holds it, so this is safe when one IS running.
python3 - <<'PY' 2>/dev/null || true
from PyQt6.QtCore import QSharedMemory
s = QSharedMemory("PinballUX")
if s.attach():
    s.detach()
PY

exec python3 run_pinballux.py
