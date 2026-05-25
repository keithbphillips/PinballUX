#!/usr/bin/env python3
"""Generate a placeholder PNG icon for PinballUX.

Run manually or called by build-appimage.sh when no pinballux.png is present.
Replace packaging/appimage/pinballux.png with real artwork to skip this script.
"""
import sys
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new('RGBA', (SIZE, SIZE), (10, 10, 20, 255))
draw = ImageDraw.Draw(img)

# Playfield surface
draw.rounded_rectangle([20, 20, 236, 236], radius=30, fill=(0, 80, 160, 255))

# Left flipper guide
draw.arc([40, 160, 120, 240], start=180, end=90, fill=(220, 220, 50, 255), width=8)
# Right flipper guide
draw.arc([136, 160, 216, 240], start=270, end=0, fill=(220, 220, 50, 255), width=8)

# Ball
draw.ellipse([108, 100, 148, 140], fill=(220, 220, 220, 255))

output = sys.argv[1] if len(sys.argv) > 1 else 'pinballux.png'
img.save(output)
print(f"Icon written to {output}")
