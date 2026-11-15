#!/usr/bin/env bash
# Share PinballUX's Tables and ROMs folders on the local network (Samba), so tables
# and ROMs can be dragged onto the cabinet from any PC, Mac or phone:
#
#     Windows:  \\<hostname>\Tables   \\<hostname>\Roms
#     macOS:    smb://<hostname>.local/Tables
#
# A file dropped there is live immediately (Table Manager -> scan to add new tables).
#
# Usage:
#     sudo raspberry-pi/setup-samba.sh [user] [tables-dir] [roms-dir]
#
# Defaults: the user who ran sudo, and the folders of the PinballUX checkout this
# script lives in. raspberry-pi/install.sh --samba runs it for you.
#
# Safe to re-run: it only rewrites the block between the PINBALLUX markers in
# /etc/samba/smb.conf and leaves the rest of the file alone.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root. Re-run:  sudo $0 $*" >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
OWNER="${1:-${SUDO_USER:-}}"
TABLES_DIR="${2:-$REPO_DIR/pinballux/data/tables}"
ROMS_DIR="${3:-$REPO_DIR/pinballux/data/roms}"
SMB_CONF="/etc/samba/smb.conf"

if [ -z "$OWNER" ] || [ "$OWNER" = "root" ] || ! id "$OWNER" >/dev/null 2>&1; then
    echo "Give the cabinet's login user:  sudo $0 <user>" >&2
    exit 1
fi
GROUP="$(id -gn "$OWNER")"

for d in "$TABLES_DIR" "$ROMS_DIR"; do
    if [ ! -d "$d" ]; then
        echo "Folder missing: $d (run raspberry-pi/install.sh first)" >&2
        exit 1
    fi
done

# --- install Samba if needed -------------------------------------------------
if ! command -v smbd >/dev/null 2>&1; then
    echo ">> Installing Samba..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y samba avahi-daemon
else
    echo ">> Samba already installed."
fi

# --- write the managed share block --------------------------------------------
BEGIN="# >>> PINBALLUX SHARES (managed by setup-samba.sh) >>>"
END="# <<< PINBALLUX SHARES <<<"

if grep -qF "$BEGIN" "$SMB_CONF" 2>/dev/null; then
    echo ">> Updating the existing PinballUX share block."
    cp "$SMB_CONF" "$SMB_CONF.bak-pinballux"
    # Delete from the BEGIN line through the END line (fixed-string match)
    awk -v b="$BEGIN" -v e="$END" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$SMB_CONF.bak-pinballux" > "$SMB_CONF"
else
    echo ">> Adding the PinballUX share block."
    cp "$SMB_CONF" "$SMB_CONF.bak-pinballux"
fi

share() {  # name, comment, path
    cat <<EOF
[$1]
   comment = $2
   path = $3
   browseable = yes
   read only = no
   guest ok = no
   valid users = $OWNER
   force user = $OWNER
   force group = $GROUP
   create mask = 0664
   directory mask = 0775

EOF
}

{
    echo "$BEGIN"
    share Tables "PinballUX tables (.vpx and .directb2s)" "$TABLES_DIR"
    share Roms "PinballUX PinMAME ROMs (.zip)" "$ROMS_DIR"
    echo "$END"
} >> "$SMB_CONF"

echo ">> Checking the configuration..."
if ! testparm -s >/dev/null 2>&1; then
    echo "smb.conf failed validation; restoring the previous file ($SMB_CONF.bak-pinballux)." >&2
    cp "$SMB_CONF.bak-pinballux" "$SMB_CONF"
    exit 1
fi

echo ">> Enabling and restarting Samba..."
systemctl enable smbd >/dev/null 2>&1 || true
systemctl restart smbd

# --- mDNS (<hostname>.local, and the shares show up in macOS Finder) --------------
if command -v avahi-daemon >/dev/null 2>&1; then
    systemctl unmask avahi-daemon.socket avahi-daemon.service >/dev/null 2>&1 || true
    systemctl enable --now avahi-daemon >/dev/null 2>&1 || true
    install -d /etc/avahi/services
    cat > /etc/avahi/services/pinballux-smb.service <<'AVAHI'
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">PinballUX (%h)</name>
  <service>
    <type>_smb._tcp</type>
    <port>445</port>
  </service>
</service-group>
AVAHI
    systemctl restart avahi-daemon >/dev/null 2>&1 || true
fi

# --- Samba password ----------------------------------------------------------------
if ! pdbedit -L 2>/dev/null | grep -q "^$OWNER:"; then
    if [ -t 0 ]; then
        echo
        echo ">> Choose the password for network access (user '$OWNER'):"
        smbpasswd -a "$OWNER"
    else
        NEED_PW=1
    fi
fi

HOST="$(hostname)"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Shares are live:"
echo "   Windows:  \\\\$HOST\\Tables   \\\\$HOST\\Roms   (or \\\\$IP\\Tables)"
echo "   macOS:    smb://$HOST.local/Tables"
echo "   Sign in as '$OWNER' with the Samba password."
if [ "${NEED_PW:-0}" = 1 ]; then
    echo "   No Samba password yet. Set one with:  sudo smbpasswd -a $OWNER"
fi
