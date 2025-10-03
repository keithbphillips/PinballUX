#!/bin/bash
# PinballUX Launcher Script
# Double-click this file to launch PinballUX

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR"

# Activate the virtual environment
source .venv/bin/activate

# Run PinballUX
python run_pinballux.py

# Keep the terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    echo "PinballUX exited with an error. Press Enter to close..."
    read
fi
