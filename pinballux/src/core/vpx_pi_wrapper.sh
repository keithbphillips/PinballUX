#!/bin/bash
# Run VPinball for one table on a Raspberry Pi, suspending the PinballUX frontend
# while the table is on screen and resuming it when the table exits.
#
# Usage (PinballUX does this itself, see core/vpx_launcher.py):
#     vpx_pi_wrapper.sh /path/to/VPinballX_GL [VPinball arguments...] table.vpx
#
# Why suspend the frontend: even with its audio released, the PyQt6 frontend keeps
# running while VPinball plays: timers fire, the wheel animation repaints and labwc
# recomposites the hidden window. On the Pi 5 that takes CPU/GPU time from VPinball
# and starves its audio buffer, which is heard as popping. SIGSTOP freezes all of it.
#
# PinballUX starts this script as its direct child, so $PPID is the PinballUX
# process. VPinball runs as OUR child (not exec) so that we stay alive to resume
# the frontend afterwards. Set PINBALLUX_SUSPEND_FRONTEND=0 to skip the suspend.

VPINBALL="$1"
shift
if [ -z "$VPINBALL" ] || [ ! -x "$VPINBALL" ] || [ "$#" -eq 0 ]; then
    echo "Usage: $(basename "$0") /path/to/VPinballX_GL [args...] table.vpx" >&2
    exit 2
fi

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
# Run VPinball under XWayland, not native Wayland: under labwc a native Wayland
# window cannot choose its output, so VPinball's per-window display settings
# (playfield / backglass / DMD positions in VPinballX.ini) would be ignored.
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"
export DISPLAY="${DISPLAY:-:0}"

PINBALLUX_PID="$PPID"
SUSPEND="${PINBALLUX_SUSPEND_FRONTEND:-1}"

resume_frontend() {
    [ "$SUSPEND" = "1" ] && kill -CONT "$PINBALLUX_PID" 2>/dev/null
    return 0
}

"$VPINBALL" "$@" &
VPX_PID=$!

# ALWAYS resume the frontend, even when we are killed. PinballUX's stop_table()
# sends SIGTERM to this script; bash only runs an EXIT trap for trapped signals,
# so trap them explicitly, or the frontend would stay frozen forever.
trap 'kill "$VPX_PID" 2>/dev/null; wait "$VPX_PID" 2>/dev/null; resume_frontend; exit 143' TERM INT HUP
trap resume_frontend EXIT

if [ "$SUSPEND" = "1" ]; then
    # Give the frontend time to paint its "Launching..." popup before freezing it;
    # the frozen popup then stays on screen until VPinball's window covers it.
    sleep 1.5
    # Only freeze it if VPinball is still running (it may have failed to start).
    if kill -0 "$VPX_PID" 2>/dev/null; then
        kill -STOP "$PINBALLUX_PID" 2>/dev/null
    fi
fi

wait "$VPX_PID"
VPX_STATUS=$?
resume_frontend
trap - EXIT
exit "$VPX_STATUS"
