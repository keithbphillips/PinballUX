#!/usr/bin/env bash
# PinballUX installer for Raspberry Pi OS (64-bit, Trixie or newer, desktop image).
#
# Run it from a clone of the raspberry-pi branch, as the normal desktop user:
#
#     git clone -b raspberry-pi https://github.com/keithbphillips/PinballUX.git ~/PinballUX
#     ~/PinballUX/raspberry-pi/install.sh
#
# What it does (safe to run again; it only fills in what is missing):
#   1. installs the system packages PinballUX needs (apt, asks for your password)
#   2. downloads Visual Pinball Standalone for the Pi into ~/.local/opt/vpinball
#   3. creates the table/media/ROM folders and points PinballUX's config at them
#   4. adds PinballUX, PinballUX Setup and PinballUX Table Manager to the menu
#
# Options:
#   --autostart          start PinballUX automatically when the desktop logs in
#   --samba              also share the Tables and ROMs folders on the network
#   --skip-vpinball      don't download Visual Pinball (use your own build)
#   --reinstall-vpinball download Visual Pinball again even if it is installed
#   -h, --help           show this help

set -euo pipefail

VPINBALL_URL="https://github.com/vpinball/vpinball/releases/download/v10.8.0-2051-28dd6c3/VPinballX_GL-10.8.0-2052-5a81d4e-Release-linux-aarch64-rpi.zip"
VPINBALL_MIN_GLIBC="2.39"   # what the VPinball build above is linked against

APT_PACKAGES=(
    python3 python3-pyqt6 python3-pyqt6.qtmultimedia python3-pygame
    python3-sqlalchemy python3-requests python3-olefile
    libxcb-cursor0          # Qt's X11 (XWayland) platform plugin
    ffmpeg                  # ffplay plays the frontend's sound effects
    unclutter-xfixes        # hides the mouse pointer over VPinball's windows
    curl unzip git
)

AUTOSTART=0; SAMBA=0; SKIP_VPX=0; REINSTALL_VPX=0
for arg in "$@"; do
    case "$arg" in
        --autostart) AUTOSTART=1 ;;
        --samba) SAMBA=1 ;;
        --skip-vpinball) SKIP_VPX=1 ;;
        --reinstall-vpinball) REINSTALL_VPX=1 ;;
        -h|--help) sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $arg (see --help)" >&2; exit 2 ;;
    esac
done

if [ -t 1 ]; then
    BOLD=$'\e[1m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; RED=$'\e[31m'; RESET=$'\e[0m'
else
    BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi
step() { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$RESET"; }
ok()   { printf '%s  ok%s %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '%s  warning:%s %s\n' "$YELLOW" "$RESET" "$1"; }
die()  { printf '%serror:%s %s\n' "$RED" "$RESET" "$1" >&2; exit 1; }

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
DATA_DIR="$REPO_DIR/pinballux/data"
VPX_DIR="$HOME/.local/opt/vpinball"
VPX_EXE="$VPX_DIR/VPinballX_GL"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
CONFIG_FILE="$HOME/.config/pinballux/config.json"

# --------------------------------------------------------------------------
step "Checking this system"

[ "$(id -u)" -ne 0 ] || die "run this as your normal user, not with sudo (it asks for sudo when needed)."
[ -f "$REPO_DIR/run_pinballux.py" ] || die "can't find run_pinballux.py next to this script; run it from a PinballUX clone."

ARCH="$(uname -m)"
[ "$ARCH" = "aarch64" ] || die "this needs 64-bit Raspberry Pi OS (found '$ARCH'). Flash the 64-bit image with Raspberry Pi Imager."
ok "64-bit ARM ($ARCH)"

# shellcheck disable=SC1091
. /etc/os-release
ok "${PRETTY_NAME:-unknown OS}"

GLIBC="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')"
if [ -n "$GLIBC" ] && [ "$(printf '%s\n%s\n' "$VPINBALL_MIN_GLIBC" "$GLIBC" | sort -V | head -1)" != "$VPINBALL_MIN_GLIBC" ]; then
    die "Visual Pinball needs glibc $VPINBALL_MIN_GLIBC or newer; this system has $GLIBC (${VERSION_CODENAME:-older release}).
       Flash the current Raspberry Pi OS (Trixie or newer) and run this again."
fi
ok "glibc ${GLIBC:-unknown}"

MODEL="$( { tr -d '\0' < /proc/device-tree/model; } 2>/dev/null || true)"
case "$MODEL" in
    *"Raspberry Pi 5"*|*"Raspberry Pi 500"*|*"Compute Module 5"*) ok "$MODEL" ;;
    *"Raspberry Pi"*) warn "$MODEL: PinballUX is tuned for the Pi 5; older boards will be slow with Visual Pinball." ;;
    *) warn "this doesn't look like a Raspberry Pi (${MODEL:-no model found}); continuing anyway." ;;
esac

if ! command -v labwc >/dev/null 2>&1 && [ -z "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then
    warn "no desktop found. PinballUX needs the Raspberry Pi OS *desktop* image (not Lite)."
fi

# --------------------------------------------------------------------------
step "Installing system packages (sudo)"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}" \
    || die "apt could not install the packages above."
PYGAME_HIDE_SUPPORT_PROMPT=1 python3 -c 'import PyQt6.QtMultimedia, sqlalchemy, pygame' 2>/dev/null \
    || die "Python packages installed but PyQt6/SQLAlchemy/pygame still don't import."
ok "system packages"

# --------------------------------------------------------------------------
step "Visual Pinball Standalone"
if [ "$SKIP_VPX" = 1 ]; then
    warn "skipped (--skip-vpinball); set the executable in PinballUX Setup."
elif [ -x "$VPX_EXE" ] && [ "$REINSTALL_VPX" = 0 ]; then
    ok "already installed in $VPX_DIR (use --reinstall-vpinball to replace it)"
else
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    echo "  downloading $(basename "$VPINBALL_URL") (~90 MB)"
    curl -fL --progress-bar -o "$TMP/vpx.zip" "$VPINBALL_URL" || die "download failed."
    unzip -q "$TMP/vpx.zip" -d "$TMP/zip"
    TARBALL="$(find "$TMP/zip" -maxdepth 1 -name '*.tar.gz' | head -1)"
    [ -n "$TARBALL" ] || die "the download doesn't contain the expected .tar.gz."
    mkdir -p "$TMP/vpx"
    tar -xzf "$TARBALL" -C "$TMP/vpx"
    [ -x "$TMP/vpx/VPinballX_GL" ] || die "VPinballX_GL not found in the download."
    rm -rf "$VPX_DIR"
    mkdir -p "$(dirname "$VPX_DIR")"
    mv "$TMP/vpx" "$VPX_DIR"
    ok "installed to $VPX_DIR"
fi

if [ -x "$VPX_EXE" ]; then
    MISSING="$( (ldd "$VPX_EXE" 2>/dev/null || true) | awk '/not found/ {print $1}' | tr '\n' ' ')"
    [ -z "$MISSING" ] || warn "Visual Pinball is missing libraries: $MISSING"

    # Setup can only write VPinball's display settings into an existing VPinballX.ini,
    # and the Pi build doesn't create one until a table has been played.
    if [ ! -f "$HOME/.vpinball/VPinballX.ini" ] && [ -f "$VPX_DIR/assets/Default_VPinballX.ini" ]; then
        mkdir -p "$HOME/.vpinball"
        cp "$VPX_DIR/assets/Default_VPinballX.ini" "$HOME/.vpinball/VPinballX.ini"
        ok "created ~/.vpinball/VPinballX.ini from VPinball's defaults"
    fi
fi

# --------------------------------------------------------------------------
step "Folders and configuration"
mkdir -p "$DATA_DIR/tables" "$DATA_DIR/media" "$DATA_DIR/roms"
ok "tables: $DATA_DIR/tables"
ok "media:  $DATA_DIR/media"
ok "ROMs:   $DATA_DIR/roms (PinballUX links ~/.pinmame/roms here when it starts)"

# Point the config at this install. Only empty paths and the .deb defaults under
# /opt/pinballux are replaced, so a configured cabinet keeps its own paths.
python3 - "$CONFIG_FILE" "$VPX_EXE" "$DATA_DIR/tables" "$DATA_DIR/media" "$SKIP_VPX" <<'PY'
import json, os, sys
path, exe, tables, media, skip_vpx = sys.argv[1:]
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    with open(path) as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}
except ValueError:
    print(f"  warning: {path} is not valid JSON; leaving it alone")
    sys.exit(0)
vpx = data.setdefault("vpx", {})
wanted = {"table_directory": tables, "media_directory": media}
if skip_vpx != "1":
    wanted["executable_path"] = exe
changed = []
for key, value in wanted.items():
    current = vpx.get(key) or ""
    if not current or current.startswith("/opt/pinballux/"):
        vpx[key] = value
        changed.append(key)
if "displays" not in data:
    # Same default PinballUX creates: wheel on the first screen, nothing else yet
    data["displays"] = {"playfield": {"name": "Playfield", "screen_number": 0, "rotation": 0, "enabled": True},
                        "backglass": None, "dmd": None, "fulldmd": None, "topper": None}
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f, indent=2)
os.replace(tmp, path)
print("  ok config: " + (", ".join(changed) + " set" if changed else "paths already set, unchanged") + f" ({path})")
PY

# --------------------------------------------------------------------------
step "Menu entries and launchers"
mkdir -p "$BIN_DIR" "$APP_DIR"

write_launcher() {  # name, python script (relative to the repo), extra lines
    cat > "$BIN_DIR/$1" <<EOF
#!/bin/bash
# Generated by PinballUX raspberry-pi/install.sh
cd "$REPO_DIR" || exit 1
$3
exec python3 "$REPO_DIR/$2" "\$@"
EOF
    chmod +x "$BIN_DIR/$1"
}
write_launcher pinballux run_pinballux.py \
'# Hide the pointer on the whole X display, so it also disappears over VPinball
if command -v unclutter >/dev/null 2>&1 && ! pgrep -u "$(id -u)" -x unclutter >/dev/null; then
    unclutter --idle 0 --start-hidden >/dev/null 2>&1 &
fi'
write_launcher pinballux-setup setup_gui.py ""
write_launcher pinballux-manager table_manager.py ""

write_desktop() {  # file, name, comment, command
    cat > "$APP_DIR/$1" <<EOF
[Desktop Entry]
Type=Application
Name=$2
Comment=$3
Exec=$BIN_DIR/$4
Path=$REPO_DIR
Icon=$REPO_DIR/pinballux.png
Terminal=false
Categories=Game;ArcadeGame;
EOF
}
write_desktop pinballux.desktop "PinballUX" "Visual Pinball cabinet frontend" pinballux
write_desktop pinballux-setup.desktop "PinballUX Setup" "Configure displays, controls and paths" pinballux-setup
write_desktop pinballux-manager.desktop "PinballUX Table Manager" "Scan tables and download media" pinballux-manager
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
ok "Games menu: PinballUX, PinballUX Setup, PinballUX Table Manager"
ok "commands: $BIN_DIR/pinballux, pinballux-setup, pinballux-manager"

AUTOSTART_FILE="$HOME/.config/autostart/pinballux.desktop"
if [ "$AUTOSTART" = 1 ]; then
    mkdir -p "$(dirname "$AUTOSTART_FILE")"
    cp "$APP_DIR/pinballux.desktop" "$AUTOSTART_FILE"
    ok "PinballUX starts when the desktop logs in (remove $AUTOSTART_FILE to stop that)"
fi

# --------------------------------------------------------------------------
if [ "$SAMBA" = 1 ]; then
    step "Network shares (sudo)"
    sudo "$REPO_DIR/raspberry-pi/setup-samba.sh" "$(id -un)" "$DATA_DIR/tables" "$DATA_DIR/roms"
fi

# --------------------------------------------------------------------------
step "Done"
cat <<EOF
Next steps:
  1. Open ${BOLD}PinballUX Setup${RESET} (Games menu) and assign your screens: playfield,
     backglass and DMD. Save.
  2. Copy tables (.vpx and .directb2s) into  $DATA_DIR/tables
     and PinMAME ROMs (.zip) into           $DATA_DIR/roms
  3. Open ${BOLD}PinballUX Table Manager${RESET}, scan for tables and download media.
  4. Start ${BOLD}PinballUX${RESET}.

To update later:  cd "$REPO_DIR" && git pull && ./raspberry-pi/install.sh
EOF
if [ "$AUTOSTART" = 0 ]; then
    echo "To start PinballUX at login, run this again with --autostart."
fi
