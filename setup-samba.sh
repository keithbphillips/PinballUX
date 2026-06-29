#!/bin/bash
# setup-samba.sh -- expose PinballUX's tables and roms folders as network shares.
#
# After this runs, any PC/Mac/phone on the same network can drag-and-drop files
# straight into the cabinet:
#
#     Tables (.vpx / .directb2s)  ->  \\pinballwizard\Tables
#     Roms   (.zip PinMAME)       ->  \\pinballwizard\Roms
#
# Because ~/tables and ~/.pinmame/roms already point at these folders, a file
# dropped over the network is live immediately -- no copy/install step.
#
# Idempotent: safe to re-run. It rewrites only the block between the PINBALLUX
# markers in smb.conf and leaves the rest of the file alone.
#
# Usage:
#     sudo ./setup-samba.sh
#
# We deliberately do NOT set the Samba password here (so this script never
# touches your password). After it finishes, set one with:
#     sudo smbpasswd -a pinballux

set -euo pipefail

# --- must be root -----------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root. Re-run:  sudo $0" >&2
    exit 1
fi

# The cabinet's own login account owns the files; Samba clients act as this user
# so anything they drop is owned correctly and is immediately usable by VPX.
OWNER="pinballux"
HOME_DIR="$(getent passwd "$OWNER" | cut -d: -f6)"
TABLES_DIR="$HOME_DIR/PinballUX/pinballux/data/tables"
ROMS_DIR="$HOME_DIR/PinballUX/pinballux/data/roms"
SMB_CONF="/etc/samba/smb.conf"

for d in "$TABLES_DIR" "$ROMS_DIR"; do
    if [ ! -d "$d" ]; then
        echo "Expected folder missing: $d" >&2
        exit 1
    fi
done

# --- install Samba server if needed ----------------------------------------
if ! command -v smbd >/dev/null 2>&1; then
    echo ">> Installing Samba server..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y samba
else
    echo ">> Samba already installed."
fi

# --- write the managed share block -----------------------------------------
# smb.conf is created by the package; we own only the region between markers.
BEGIN="# >>> PINBALLUX SHARES (managed by setup-samba.sh) >>>"
END="# <<< PINBALLUX SHARES <<<"

# Strip any previous managed block so re-runs don't stack duplicates.
if grep -qF "$BEGIN" "$SMB_CONF" 2>/dev/null; then
    echo ">> Updating existing PinballUX share block."
    sed -i "/$(printf '%s' "$BEGIN" | sed 's/[][\.*^$/]/\\&/g')/,/$(printf '%s' "$END" | sed 's/[][\.*^$/]/\\&/g')/d" "$SMB_CONF"
else
    echo ">> Adding PinballUX share block."
fi

cat >> "$SMB_CONF" <<EOF
$BEGIN
[Tables]
   comment = PinballUX VPX tables (.vpx and .directb2s)
   path = $TABLES_DIR
   browseable = yes
   read only = no
   writable = yes
   guest ok = no
   valid users = $OWNER
   force user = $OWNER
   force group = $OWNER
   create mask = 0664
   directory mask = 0775

[Roms]
   comment = PinballUX PinMAME roms (.zip)
   path = $ROMS_DIR
   browseable = yes
   read only = no
   writable = yes
   guest ok = no
   valid users = $OWNER
   force user = $OWNER
   force group = $OWNER
   create mask = 0664
   directory mask = 0775
$END
EOF

# --- validate, enable, restart ---------------------------------------------
echo ">> Validating configuration..."
testparm -s >/dev/null

echo ">> Enabling and restarting Samba..."
systemctl enable smbd >/dev/null 2>&1 || true
systemctl restart smbd

# --- mDNS discovery (Avahi) -------------------------------------------------
# Avahi advertises "$HOSTNAME.local" so the cabinet is reachable by name from
# Windows 10/11 and macOS even without NetBIOS, and the SMB service file below
# makes it appear as a file server in macOS Finder. Some Pi images ship the
# avahi units masked, so unmask before enabling.
echo ">> Enabling Avahi (mDNS / .local) ..."
if command -v avahi-daemon >/dev/null 2>&1; then
    systemctl unmask avahi-daemon.socket avahi-daemon.service >/dev/null 2>&1 || true
    systemctl enable --now avahi-daemon >/dev/null 2>&1 || true

    install -d /etc/avahi/services
    cat > /etc/avahi/services/smb.service <<'AVAHI'
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<!-- Advertises PinballUX's Samba shares over mDNS so the cabinet appears as a
     file server in macOS Finder and is reachable at <hostname>.local. -->
<service-group>
  <name replace-wildcards="yes">PinballUX (%h)</name>
  <service>
    <type>_smb._tcp</type>
    <port>445</port>
  </service>
</service-group>
AVAHI
    systemctl restart avahi-daemon >/dev/null 2>&1 || true
else
    echo "   (avahi-daemon not present; skipping mDNS. Install 'avahi-daemon' to enable.)"
fi

# --- check whether the Samba account has a password yet ---------------------
if pdbedit -L 2>/dev/null | grep -q "^$OWNER:"; then
    HAVE_PW="yes"
else
    HAVE_PW="no"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
HOSTNAME="$(hostname)"

echo
echo "============================================================"
echo " Samba shares are live."
echo
echo "   Windows:  \\\\$HOSTNAME\\Tables   \\\\$HOSTNAME\\Roms"
echo "             (or by IP: \\\\$IP\\Tables )"
echo "   macOS:    smb://$HOSTNAME.local/Tables"
echo "   By name:  $HOSTNAME.local  (mDNS, via Avahi)"
echo
echo "   Sign in as user '$OWNER' with the Samba password."
if [ "$HAVE_PW" = "no" ]; then
    echo
    echo " !! No Samba password set yet. Set one now:"
    echo "      sudo smbpasswd -a $OWNER"
fi
echo "============================================================"
