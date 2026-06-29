#!/bin/bash
# Launch VPinball (OpenGL ES build) for a single table, suspending the PinballUX
# frontend for the whole time the table is on screen, then resuming it on exit.
#
# Why suspend the frontend: even with its audio disabled, the PyQt6 frontend
# keeps running while VPX plays -- timers fire, the wheel glow animation repaints
# ~20x/sec, and labwc recomposites the obscured window. On the Pi 5 that steals
# CPU/GPU from VPX and starves its audio buffer, heard as popping. SIGSTOP'ing
# the frontend freezes ALL of it (timers, repaints, decode, audio threads) so VPX
# gets the machine to itself. A bare launcher that does nothing during play does
# not pop -- this makes the frontend behave the same.
#
# PinballUX sets this script as vpx.executable_path and runs it as its direct
# QProcess child (no shell), passing only the table path. So $PPID IS the
# PinballUX PID. We run VPX as OUR child (not exec) and stay alive as a separate
# process; stopping our parent does not stop us, so we can resume it afterwards.
#
# Usage: vpinball.sh <table.vpx>

VPINBALL=/home/pinballux/VPinballX/VPinballX_GL

# A table path is required (PinballUX always passes one). If run by hand with
# no argument, print usage and exit rather than hardcoding a specific table.
TABLE="$1"
if [ -z "$TABLE" ]; then
    echo "Usage: vpinball.sh <table.vpx>" >&2
    exit 1
fi

export XDG_RUNTIME_DIR=/run/user/$(id -u)
# Run under XWayland (x11), NOT native Wayland. Under labwc a native-Wayland
# client cannot choose its output -- the compositor maps the window onto the
# focused output -- so VPX's per-window Display settings are ignored. XWayland
# presents the monitor(s) as one X screen so absolute window positioning is
# honored. (Same reason PinballUX itself runs under xcb/XWayland.)
export SDL_VIDEODRIVER=x11
export DISPLAY="${DISPLAY:-:0}"
# Keep a Wayland fallback handle in case anything probes it; harmless under x11.
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

# Optional: wipe this table's texture cache before launching. The old local GLES
# build could hang at "Loading Textures" with a stale cache; wiping forced a
# clean rebuild. The current release build caches fine, and a wipe costs several
# seconds of rebuild every launch -- so it's OFF by default. Set CLEAR_CACHE=1
# if a table ever hangs on load again.
CLEAR_CACHE=0
if [ "$CLEAR_CACHE" = "1" ]; then
    CACHE_DIR="/home/pinballux/.vpinball/Cache/$(basename "$TABLE" .vpx)"
    [ -n "$CACHE_DIR" ] && rm -rf "$CACHE_DIR"
fi

# This standalone build is play-only (no editor/menu); a table is required.
PINBALLUX_PID="$PPID"

resume_frontend() { [ -n "$PINBALLUX_PID" ] && kill -CONT "$PINBALLUX_PID" 2>/dev/null; }

"$VPINBALL" -EnableTrueFullscreen -Play "$TABLE" &
VPX_PID=$!

# Safety: ALWAYS resume the frontend, even if we're killed. PinballUX's
# stop_table() sends SIGTERM to this wrapper; bash runs the EXIT trap on a
# *trapped* signal but not on an untrapped default-terminate, so trap the
# signals explicitly too -- otherwise the frontend would stay frozen forever.
trap 'kill "$VPX_PID" 2>/dev/null; resume_frontend; exit 143' TERM INT HUP
trap resume_frontend EXIT

# Give the frontend a moment to paint its "LAUNCHING..." popup before freezing
# it. SIGSTOP otherwise lands within milliseconds -- before the popup renders --
# and the message never appears. VPX is still loading during this window (no
# gameplay yet, so no pops to worry about); the painted popup then stays frozen
# on screen until VPX's window covers it.
sleep 1.5
kill -STOP "$PINBALLUX_PID" 2>/dev/null   # freeze the frontend (timers/repaints/audio)
wait "$VPX_PID"                           # block until the table exits
VPX_STATUS=$?
resume_frontend                           # wake PinballUX back up
trap - EXIT
exit "$VPX_STATUS"
