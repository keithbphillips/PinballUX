# VPinball Joystick Modes

## Two Ways VPinball Handles Joysticks

### Mode 1: Joystick Mode (Recommended)
- Uses raw button numbers from VPinballX.ini
- Example: `JoyLFlipKey = 10` means physical button 10
- **Advantage:** Simpler, supports all buttons
- **No gamecontrollerdb.txt required**

### Mode 2: Gamepad Mode
- Uses SDL gamecontroller mappings from gamecontrollerdb.txt
- Maps physical buttons to standard gamepad button names (a, b, x, y, leftshoulder, etc.)
- VPinball internally maps gamepad button names to game functions
- **Advantage:** Works with XInput devices
- **Disadvantage:** VPinball's internal mapping may not match your expectations

## Current Status

Your VPinballX.ini has these joystick mappings:
```ini
JoyLFlipKey = 10
JoyRFlipKey = 11
JoyPlungerKey = 9
JoyAddCreditKey = 1
JoyLMagnaSave = 9
JoyRMagnaSave = 8
JoyStartGameKey = 7
JoyExitGameKey = 3
```

Your working gamecontrollerdb.txt line:
```
03000000790000000600000010010000,DragonRise Inc. Generic USB Joystick,platform:Linux,a:b1,rightstick:b9,x:b3,y:b4,leftshoulder:b10,rightshoulder:b11,start:b7,back:b8,dpdown:b2
```

## Recommendation

**Use Joystick Mode** and focus on keeping VPinballX.ini updated, since:
1. It's simpler and supports all 12 buttons on your joystick
2. You have direct control over what each button does
3. The gamecontrollerdb.txt mapping has limitations (some SDL button names may not map to the VPinball functions you want)

## Implementation Decision Needed

Should PinballUX Setup:

**Option A: Joystick Mode Only**
- Skip gamecontrollerdb.txt generation entirely
- Only update VPinballX.ini with button mappings
- Simpler and more reliable

**Option B: Hybrid Mode**
- Keep your working gamecontrollerdb.txt line as-is (with correct GUID)
- Also update VPinballX.ini for joystick mode
- Covers both modes but gamecontroller mapping may not reflect current config

**Option C: Try to Generate Gamepad Mode**
- Generate gamecontrollerdb.txt from button config
- Problem: VPinball's internal SDL→function mapping may not match expectations
- Complex and may not work as expected
