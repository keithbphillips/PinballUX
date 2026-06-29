#!/bin/bash
# PinballUX Setup launcher for the Raspberry Pi 5 cabinet.
#
# Runs the PyQt6 setup tool inside the rpd-labwc desktop session. Uses the same
# Pi-specific environment as run-pi.sh:
#   QT_QPA_PLATFORM=xcb  -> run under XWayland (Qt wayland plugin not installed)

cd "$(dirname "$(readlink -f "$0")")" || exit 1

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export QT_QPA_PLATFORM=xcb

exec python3 setup_gui.py
