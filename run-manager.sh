#!/bin/bash
# PinballUX Table Manager launcher for the Raspberry Pi 5 cabinet.
#
# Runs the PyQt6 table manager inside the rpd-labwc desktop session. Uses the
# same Pi-specific environment as run-pi.sh:
#   QT_QPA_PLATFORM=xcb            -> run under XWayland (Qt wayland plugin not
#                                     installed)
#   QT_FFMPEG_DECODING_HW_DEVICE_TYPES=""
#                                  -> force SOFTWARE video decode. The Pi 5 has
#                                     no H.264 hardware decoder; the manager's
#                                     media previews otherwise try h264_v4l2m2m,
#                                     fail, and hang.

cd "$(dirname "$(readlink -f "$0")")" || exit 1

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export QT_QPA_PLATFORM=xcb
export QT_FFMPEG_DECODING_HW_DEVICE_TYPES=""

exec python3 table_manager.py
