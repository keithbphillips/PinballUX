# Joystick Mapping System

## Overview

PinballUX automatically configures joystick mappings for VPinball by detecting the connected joystick's GUID and generating SDL game controller mappings.

## How It Works

### 1. Joystick Detection
When the user runs `pinballux-setup`, the system:
- Detects the connected joystick using pygame
- Reads the joystick's unique GUID (e.g., `0300457e790000000600000010010000`)
- Captures button mappings from user input

### 2. Configuration Files Updated

The setup process updates THREE configuration files:

#### a) `~/.config/pinballux/config.json`
PinballUX's own configuration with joystick button mappings:
```json
{
  "input": {
    "joystick_enabled": true,
    "joystick_buttons": {
      "LEFT_FLIPPER": 10,
      "RIGHT_FLIPPER": 11,
      "START": 7,
      ...
    }
  }
}
```

#### b) `~/.vpinball/VPinballX.ini`
VPinball's configuration (button numbers only):
```ini
[Player]
JoyLFlipKey = 11
JoyRFlipKey = 12
JoyStartGameKey = 8
...
```

**Note:** VPinball uses 1-based button numbering (button 0 = value 1)

#### c) `~/.vpinball/gamecontrollerdb.txt`
SDL game controller database with GUID-specific mappings:
```
0300457e790000000600000010010000,DragonRise Inc. Generic USB Joystick,platform:Linux,leftshoulder:b10,rightshoulder:b11,start:b7,back:b8,a:b1,b:b2,x:b3,y:b4,guide:b9
```

### 3. Automatic GUID Handling

**Key Feature:** Each joystick has a unique GUID that SDL/pygame can detect automatically.

- When a user runs setup on their machine, the system detects *their* joystick's GUID
- The mapping is written with that specific GUID
- Works with ANY joystick model - no hardcoding needed!

## For Different Users

### Same Joystick Model
If two users have the same joystick model:
- They'll likely get the same GUID
- Their mappings will automatically match
- No additional configuration needed

### Different Joystick Models
If users have different joysticks:
- Each gets their own unique GUID
- Each mapping is stored separately in `gamecontrollerdb.txt`
- VPinball uses the correct mapping based on the connected joystick

## Implementation

### Core Components

1. **`gamecontroller_manager.py`** - Manages SDL game controller database
   - `normalize_guid()` - Normalizes pygame GUID to SDL2 standard format
   - `get_joystick_info()` - Detects joystick and reads GUID (normalized)
   - `generate_mapping_string()` - Creates SDL mapping from button config
   - `update_from_button_mappings()` - Writes mapping to database

2. **`setup_gui.py`** - Setup GUI integration
   - `JoystickConfigTab._save_to_gamecontroller_db()` - Called during save
   - Automatically updates gamecontroller database when user maps buttons

### SDL Mapping Format

Format: `GUID,Name,platform:Linux,button:bN,button2:bN,...`

Button name mappings:
- `leftshoulder` / `rightshoulder` - Flipper buttons (L1/R1, LB/RB)
- `start` - Start button
- `back` - Menu/Select button
- `a` - Main action button (Select/Launch)
- `b` - Secondary button (Plunger)
- `x` / `y` - Additional buttons (MagnaSave)
- `guide` - Exit/Home button

## Testing

Test the gamecontroller manager:
```bash
python3 gamecontroller_manager.py
```

This will:
- Detect your joystick
- Show GUID, name, button count
- Generate example SDL mapping string

## GUID Normalization

**Important:** Pygame sometimes returns GUIDs in a different format than SDL2/VPinball expects.

### The Issue
- **Pygame GUID format:** `0300457e790000000600000010010000` (has extra bytes at positions 4-7)
- **SDL2 standard format:** `03000000790000000600000010010000` (expected by VPinball)

VPinball only recognizes the SDL2 standard format!

### The Solution
The `GameControllerManager.normalize_guid()` function automatically converts pygame's GUID to the SDL2 standard format by:

1. Detecting non-standard format (bytes 4-7 not "0000")
2. Extracting vendor ID (bytes 8-11) and product ID (bytes 16-19)
3. Reconstructing in standard format: `03000000VVVVPPPPVVVV000000000000`

Example:
```python
pygame_guid = "0300457e790000000600000010010000"
sdl_guid    = "03000000790000000600000010010000"  # normalized
```

This happens automatically - you don't need to do anything!

## Troubleshooting

### No joystick detected
- Ensure joystick is connected
- Check with `jstest /dev/input/js0`
- Verify pygame installation

### Wrong GUID in database
- The system automatically normalizes GUIDs
- If still wrong, check USB device ID: `lsusb | grep -i joystick`
- Expected format: `03000000VVVVPPPPVVVV000000000000`
  - `VVVV` = vendor ID (e.g., `0079` becomes `7900` in little-endian)
  - `PPPP` = product ID (e.g., `0006` becomes `0600` in little-endian)

### VPinball not recognizing buttons
- Check VPinball's log: `~/.vpinball/vpinball.log`
- Verify gamecontrollerdb.txt has entry for your joystick's GUID
- Ensure GUID matches SDL2 format (not pygame format)
- Ensure button numbers match in VPinballX.ini

## Benefits

✅ **Portable** - Works on any machine with any joystick
✅ **Automatic** - No manual GUID configuration needed
✅ **Multi-joystick** - Supports multiple joystick models simultaneously
✅ **Standard** - Uses SDL2 game controller database format
✅ **Integrated** - Setup GUI handles everything automatically
