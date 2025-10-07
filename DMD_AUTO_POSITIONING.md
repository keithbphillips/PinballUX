# DMD Auto-Positioning Feature

## Overview

The setup GUI now includes automatic DMD positioning that intelligently places and sizes DMD windows based on screen resolution and pinball cabinet layout requirements.

## How It Works

### The Problem

Pinball cabinets use separate DMD (Dot Matrix Display) screens that need precise positioning:
- DMD must be centered horizontally
- DMD must be in the lower portion of the screen
- DMD must align with the dark space in FullDMD images
- Size must scale appropriately for different screen resolutions

Manual positioning is tedious and error-prone.

### The Solution

**Automatic DMD Positioning** - One-click button that:
1. Detects selected screen resolution
2. Calculates optimal DMD size based on resolution
3. Centers DMD horizontally
4. Positions DMD in lower portion (70-80% down)
5. Updates VPinballX.ini with calculated values

## Features

### Intelligent Sizing

DMD size automatically scales with resolution:

| Screen Resolution | DMD Size | Scale Factor |
|-------------------|----------|--------------|
| 1920x1080 (1080p) | 384x96   | 3.0x         |
| 1920x1200         | 448x112  | 3.5x         |
| 2560x1440 (1440p) | 512x128  | 4.0x         |
| 3840x2160 (4K)    | 768x192  | 6.0x         |

### Smart Positioning

Different DMD types are positioned optimally:

- **PinMAME DMD** (`dmd`) - 80% down the screen
  - For ROM-based classic tables
  - Smaller, positioned lower

- **FlexDMD** (`fulldmd`) - 70% down the screen
  - For modern tables with custom DMD artwork
  - Larger, centered in lower portion

- **B2S DMD** (`b2sdmd`) - 70% down the screen
  - Same as FlexDMD
  - Aligns with B2S backglass DMD cutouts

### Example Positions

#### 1920x1080 Landscape Screen:
```
DMD (PinMAME):
  Position: (768, 816)
  Size: 384x96
  Center: 80% down screen

FullDMD (FlexDMD):
  Position: (768, 708)
  Size: 384x96
  Center: 70% down screen
```

#### 1080x1920 Portrait Screen:
```
DMD (PinMAME):
  Position: (199, 1451)
  Size: 682x170
  Center: 80% down screen
```

## Using the Feature

### In Setup GUI

1. Open PinballUX Setup: `python3 setup_gui.py`
2. Go to **Displays** tab
3. Expand DMD display section (DMD, FullDMD, or B2SDMD)
4. Select the screen from dropdown
5. Click **🎯 Auto-Position DMD** button
6. Verify the calculated position
7. Click **Save Configuration**

### What Gets Updated

The auto-position feature updates VPinballX.ini:

```ini
[Standalone]
# For PinMAME DMD
PinMAMEWindowX = 1920        # Screen X offset
PinMAMEWindowY = 0           # Screen Y offset
PinMAMEWindowWidth = 384     # DMD width
PinMAMEWindowHeight = 96     # DMD height

# For FlexDMD
FlexDMDWindowX = 1920
FlexDMDWindowY = 0
FlexDMDWindowWidth = 384
FlexDMDWindowHeight = 96
```

## Technical Details

### DMD Aspect Ratios

Supports multiple DMD types:

- **Classic** (4:1) - 128x32 base - Traditional Bally/Williams
- **Wide** (3:1) - 192x64 base - Modern wider DMDs
- **Tall** (2:1) - 128x64 base - Taller DMDs

### Calculation Algorithm

```python
1. Get screen resolution (width, height)
2. Select DMD aspect ratio (classic = 128x32)
3. Calculate scale factor based on screen height
4. Multiply base dimensions by scale
5. Center horizontally: x = (width - dmd_width) / 2
6. Position vertically: y = (height * 0.70) - (dmd_height / 2)
7. Add screen offset for multi-monitor setups
```

### Multi-Monitor Support

For cabinets with multiple screens:
- Screen offset is automatically added
- DMD position is calculated relative to its designated screen
- Works with any screen in any position

## Benefits

✅ **No Manual Math** - Automatically calculates positions
✅ **Resolution Independent** - Works with any screen size
✅ **Consistent** - Always centers and positions correctly
✅ **Fast** - One click instead of trial and error
✅ **Multi-Monitor** - Handles complex cabinet setups
✅ **Scalable** - Adapts DMD size to screen resolution

## Files

### Core Implementation

- **`dmd_position_calculator.py`** - DMD positioning calculation engine
  - `DMDPositionCalculator` class
  - `calculate_dmd_position()` - Main calculation method
  - `calculate_for_cabinet_screens()` - Cabinet-specific configs

- **`setup_gui.py`** - GUI integration
  - Auto-Position button in DMD display sections
  - `_auto_position_dmd()` - Button click handler
  - Integrated with display configuration system

### Testing

- **`test_dmd_autoposition.py`** - Position calculation verification
- **`dmd_position_calculator.py`** - Includes built-in test mode

## Testing

```bash
# Test the calculator
python3 dmd_position_calculator.py

# Test auto-positioning logic
python3 test_dmd_autoposition.py

# Test in GUI
python3 setup_gui.py
```

## Future Enhancements

Potential improvements:

1. **Custom Vertical Position** - User-adjustable percentage
2. **DMD Size Presets** - Small/Medium/Large options
3. **Preview Window** - Show DMD position before saving
4. **Image Detection** - Analyze FullDMD image to find DMD cutout automatically
5. **Multiple DMD Support** - Position multiple DMDs on same screen

## Troubleshooting

### DMD Too Large
- Calculator automatically limits to 90% screen width, 25% screen height
- Manually reduce scale in calculator if needed

### DMD Too Small
- Increase resolution or manually adjust size
- Use scale_override parameter for custom sizing

### Position Not Centered
- Verify screen is selected correctly
- Check for screen offset in multi-monitor setup
- Recalculate after changing screen selection

### DMD Not Aligning with Image
- FullDMD images vary - may need manual adjustment
- Use calculated position as starting point
- Fine-tune with arrow keys in VPX fields
