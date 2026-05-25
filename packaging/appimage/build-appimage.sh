#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
VERSION="$(cat "$PROJECT_ROOT/VERSION")"
ARCH="$(uname -m)"

echo "==> Building PinballUX $VERSION AppImage ($ARCH)"

# --- appimagetool ---
APPIMAGETOOL="$SCRIPT_DIR/appimagetool-${ARCH}.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "==> Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage" \
        -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

# Run appimagetool without FUSE (required in Docker/CI environments)
export APPIMAGE_EXTRACT_AND_RUN=1

# --- Python virtual environment ---
VENV="$BUILD_DIR/venv"
echo "==> Setting up Python environment..."
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q pyinstaller pyinstaller-hooks-contrib
pip install -q -r "$PROJECT_ROOT/requirements.txt"

# --- Generate placeholder icon if one is not already present ---
ICON="$SCRIPT_DIR/pinballux.png"
if [ ! -f "$ICON" ]; then
    echo "==> Generating placeholder icon..."
    python3 "$SCRIPT_DIR/generate_icon.py" "$ICON"
fi

# --- PyInstaller ---
echo "==> Running PyInstaller..."
pyinstaller "$SCRIPT_DIR/pinballux.spec" \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/work" \
    --noconfirm

# --- Assemble AppDir ---
APPDIR="$BUILD_DIR/PinballUX.AppDir"
echo "==> Assembling AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/opt"

cp -r "$BUILD_DIR/dist/pinballux" "$APPDIR/opt/pinballux"

cp "$SCRIPT_DIR/AppDir/AppRun"             "$APPDIR/AppRun"
cp "$SCRIPT_DIR/AppDir/pinballux.desktop"  "$APPDIR/pinballux.desktop"
cp "$ICON"                                 "$APPDIR/pinballux.png"
cp "$ICON"                                 "$APPDIR/.DirIcon"
chmod +x "$APPDIR/AppRun"

# --- Build AppImage ---
OUTPUT="$PROJECT_ROOT/PinballUX-${VERSION}-${ARCH}.AppImage"
echo "==> Building AppImage..."
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

echo ""
echo "Done: $OUTPUT"
