#!/bin/bash
# PinballUX Installation Script
# This script installs PinballUX and its dependencies on Ubuntu/Debian systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo -e "${RED}Error: Please do not run this script as root or with sudo${NC}"
   echo "The script will ask for sudo password when needed"
   exit 1
fi

echo -e "${GREEN}PinballUX Installation Script${NC}"
echo "=============================="
echo

# Find the .deb file
DEB_FILE=$(ls pinballux_*.deb 2>/dev/null | head -n 1)

if [ -z "$DEB_FILE" ]; then
    echo -e "${RED}Error: No .deb package found in current directory${NC}"
    echo "Please download or build the PinballUX package first"
    exit 1
fi

echo -e "Found package: ${GREEN}$DEB_FILE${NC}"
echo

# Copy .deb to /tmp for apt to access (avoids permission issues)
TMP_DEB="/tmp/$(basename "$DEB_FILE")"
echo "Copying package to /tmp for installation..."
cp "$DEB_FILE" "$TMP_DEB"
chmod 644 "$TMP_DEB"
DEB_FILE="$TMP_DEB"
echo

# Check if gdebi is installed
if command -v gdebi &> /dev/null; then
    echo "Installing with gdebi..."
    sudo gdebi -n "$DEB_FILE"
else
    echo "gdebi not found. Installing dependencies first..."
    echo

    # Install with dpkg
    echo "Installing package..."
    sudo dpkg -i "$DEB_FILE" 2>&1 || true

    echo
    echo "Installing missing dependencies..."
    sudo apt-get update
    sudo apt-get install -f -y
fi

echo
echo -e "${GREEN}Installation complete!${NC}"

# Cleanup temp file
if [ -f "$TMP_DEB" ]; then
    rm -f "$TMP_DEB"
fi

echo
echo "Next steps:"
echo "  1. Run 'pinballux-setup' to configure displays and controls"
echo "  2. Run 'pinballux-manager' to scan tables and download media"
echo "  3. Run 'pinballux' to launch the application"
echo
echo "For help, visit: https://github.com/keithbphillips/PinballUX"
