#!/usr/bin/env python3
"""
Combined Joystick Button Mapping Tool
Configures buttons for both PinballUX frontend AND Visual Pinball gameplay
"""

import pygame
import sys
import json
from pathlib import Path
from typing import Dict, Optional

# Frontend actions (PinballUX only)
FRONTEND_ACTIONS = [
    ('WHEEL_LEFT', 'Navigate tables left', None),
    ('WHEEL_RIGHT', 'Navigate tables right', None),
    ('SELECT', 'Launch selected table', None),
]

# Gameplay actions (Visual Pinball - these also work in PinballUX)
# Example VPX config values:
#   JoyLFlipKey = 10, JoyRFlipKey = 11
#   JoyPlungerKey = 7, JoyAddCreditKey = 1
#   JoyLMagnaSave = 9, JoyRMagnaSave = 8
#   JoyStartGameKey = 2, JoyExitGameKey = 3
GAMEPLAY_ACTIONS = [
    ('FLIPPERS', 'Left/Right flippers', ['JoyLFlipKey', 'JoyRFlipKey']),  # Will ask twice
    ('PLUNGER', 'Launch ball', 'JoyPlungerKey'),
    ('START', 'Start game', 'JoyStartGameKey'),
    ('MENU', 'Open menu / Add credit', 'JoyAddCreditKey'),
    ('MAGNASAVE', 'MagnaSave buttons', ['JoyLMagnaSave', 'JoyRMagnaSave']),  # Will ask twice
    ('EXIT_TABLE', 'Exit table (VPX only)', 'JoyExitGameKey'),
]


def get_config_path() -> Path:
    """Get the PinballUX config file path"""
    return Path.home() / ".config" / "pinballux" / "config.json"


def get_vpx_config_path() -> Path:
    """Get the VPX config file path"""
    return Path.home() / ".vpinball" / "VPinballX.ini"


def load_config() -> dict:
    """Load existing PinballUX config"""
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    """Save PinballUX config to file"""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✓ PinballUX config saved to {config_path}")


def save_vpx_config_surgical(button_mappings: dict):
    """Save VPX joystick button mappings without touching other settings

    This does a surgical edit - only updates joystick button lines,
    preserving all other settings and formatting in the file.
    """
    vpx_path = get_vpx_config_path()
    if not vpx_path.exists():
        print(f"✗ VPX config not found at {vpx_path}")
        return

    # Create backup before making any changes
    import shutil
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = vpx_path.parent / f"VPinballX.ini.backup_{timestamp}"
    shutil.copy2(vpx_path, backup_path)
    print(f"✓ Created backup: {backup_path}")

    # Read the entire file
    with open(vpx_path, 'r') as f:
        lines = f.readlines()

    # Track which keys we've updated
    updated_keys = set()

    # Update existing joystick button lines
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        for key, value in button_mappings.items():
            key_lower = key.lower()
            # Check if this line is for this key
            if line_lower.startswith(f"{key_lower} =") or line_lower.startswith(f"{key_lower}="):
                # Preserve original key case from file
                original_key = line.split('=')[0].strip()
                lines[i] = f"{original_key} = {value}\n"
                updated_keys.add(key.lower())
                break

    # Add any missing keys at the end of [Player] section
    missing_keys = set(k.lower() for k in button_mappings.keys()) - updated_keys
    if missing_keys:
        # Find the [Player] section
        player_section_idx = None
        next_section_idx = None

        for i, line in enumerate(lines):
            if line.strip().lower() == '[player]':
                player_section_idx = i
            elif player_section_idx is not None and line.strip().startswith('['):
                next_section_idx = i
                break

        # Insert missing keys before the next section
        if player_section_idx is not None:
            insert_idx = next_section_idx if next_section_idx else len(lines)
            for key, value in button_mappings.items():
                if key.lower() in missing_keys:
                    lines.insert(insert_idx, f"{key} = {value}\n")

    # Write back
    with open(vpx_path, 'w') as f:
        f.writelines(lines)

    print(f"✓ VPX config saved to {vpx_path}")


def wait_for_button(joystick) -> Optional[int]:
    """Wait for a button press and return button number"""
    print("  Press a button (or press Enter to skip)...", end='', flush=True)

    # Track initial button states
    initial_states = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]

    while True:
        pygame.event.pump()

        # Check for button presses
        for i in range(joystick.get_numbuttons()):
            current_state = joystick.get_button(i)
            # Detect new press (wasn't pressed initially, now is pressed)
            if current_state and not initial_states[i]:
                print(f" Button {i}")
                return i
            # Update state
            initial_states[i] = current_state

        # Allow skipping with Enter key (check stdin)
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline().strip()
            if line == '':
                print(" Skipped")
                return None

        pygame.time.wait(50)


def main():
    print("=" * 70)
    print("Combined Joystick Button Mapper")
    print("Configures PinballUX Frontend + Visual Pinball Gameplay")
    print("=" * 70)

    # Initialize pygame
    pygame.init()
    pygame.joystick.init()

    joystick_count = pygame.joystick.get_count()

    if joystick_count == 0:
        print("\n❌ No joystick detected!")
        print("Please connect your pinball controller and try again.")
        sys.exit(1)

    # Use first joystick
    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(f"\n✓ Detected: {joystick.get_name()}")
    print(f"  Buttons: {joystick.get_numbuttons()}")
    print(f"  Axes: {joystick.get_numaxes()}")
    print(f"  Hats: {joystick.get_numhats()}")

    # Store mappings
    pinballux_mappings = {}  # PinballUX (0-based button numbers)
    vpx_mappings = {}  # VPX ini keys (1-based button numbers)

    # Map frontend actions
    print("\n" + "=" * 70)
    print("PART 1: Frontend Navigation (PinballUX)")
    print("=" * 70)
    print("These buttons control table selection in the frontend.\n")

    for action, description, _ in FRONTEND_ACTIONS:
        print(f"\n{action} ({description})")
        button = wait_for_button(joystick)
        if button is not None:
            pinballux_mappings[action] = button

    # Map gameplay actions
    print("\n" + "=" * 70)
    print("PART 2: Gameplay Controls (Visual Pinball)")
    print("=" * 70)
    print("These buttons control actual pinball gameplay.\n")

    for action, description, vpx_key in GAMEPLAY_ACTIONS:
        # Handle FLIPPERS specially (needs two buttons)
        if action == 'FLIPPERS':
            print(f"\nLEFT FLIPPER")
            left_button = wait_for_button(joystick)
            if left_button is not None:
                pinballux_mappings['FLIPPERS'] = left_button
                vpx_mappings['JoyLFlipKey'] = left_button + 1  # VPX uses 1-based

            print(f"\nRIGHT FLIPPER")
            right_button = wait_for_button(joystick)
            if right_button is not None:
                vpx_mappings['JoyRFlipKey'] = right_button + 1  # VPX uses 1-based
        # Handle MAGNASAVE specially (needs two buttons)
        elif action == 'MAGNASAVE':
            print(f"\nLEFT MAGNASAVE")
            left_button = wait_for_button(joystick)
            if left_button is not None:
                pinballux_mappings['MAGNASAVE'] = left_button
                vpx_mappings['JoyLMagnaSave'] = left_button + 1  # VPX uses 1-based

            print(f"\nRIGHT MAGNASAVE")
            right_button = wait_for_button(joystick)
            if right_button is not None:
                vpx_mappings['JoyRMagnaSave'] = right_button + 1  # VPX uses 1-based
        else:
            print(f"\n{action} ({description})")
            button = wait_for_button(joystick)
            if button is not None:
                # Don't add optional VPX-only actions to PinballUX
                if action != 'EXIT_TABLE':
                    pinballux_mappings[action] = button
                if vpx_key:
                    vpx_mappings[vpx_key] = button + 1  # VPX uses 1-based

    # Show summary
    print("\n" + "=" * 70)
    print("Mapping Summary")
    print("=" * 70)

    print("\n[Frontend - PinballUX]")
    frontend_mapped = False
    for action, description, _ in FRONTEND_ACTIONS:
        if action in pinballux_mappings:
            print(f"  Button {pinballux_mappings[action]:2d} -> {action:15s} ({description})")
            frontend_mapped = True
    if not frontend_mapped:
        print("  (none mapped)")

    print("\n[Gameplay - Visual Pinball]")
    gameplay_mapped = False
    for action, description, vpx_key in GAMEPLAY_ACTIONS:
        if action == 'FLIPPERS':
            if 'JoyLFlipKey' in vpx_mappings:
                print(f"  Button {vpx_mappings['JoyLFlipKey']-1:2d} -> Left Flipper")
                gameplay_mapped = True
            if 'JoyRFlipKey' in vpx_mappings:
                print(f"  Button {vpx_mappings['JoyRFlipKey']-1:2d} -> Right Flipper")
                gameplay_mapped = True
        elif action == 'MAGNASAVE':
            if 'JoyLMagnaSave' in vpx_mappings:
                print(f"  Button {vpx_mappings['JoyLMagnaSave']-1:2d} -> Left MagnaSave")
                gameplay_mapped = True
            if 'JoyRMagnaSave' in vpx_mappings:
                print(f"  Button {vpx_mappings['JoyRMagnaSave']-1:2d} -> Right MagnaSave")
                gameplay_mapped = True
        elif action == 'EXIT_TABLE':
            # VPX-only action, check vpx_mappings
            if vpx_key and vpx_key in vpx_mappings:
                print(f"  Button {vpx_mappings[vpx_key]-1:2d} -> {action:15s} ({description})")
                gameplay_mapped = True
        elif action in pinballux_mappings:
            print(f"  Button {pinballux_mappings[action]:2d} -> {action:15s} ({description})")
            gameplay_mapped = True
    if not gameplay_mapped:
        print("  (none mapped)")

    # Save to both configs
    print("\n" + "-" * 70)
    save_choice = input("Save this configuration? (y/n): ").strip().lower()

    if save_choice == 'y':
        # Save PinballUX config
        config = load_config()
        if 'input' not in config:
            config['input'] = {}
        config['input']['joystick_buttons'] = pinballux_mappings
        config['input']['joystick_enabled'] = True
        save_config(config)

        # Save VPX config (surgical edit to preserve all other settings)
        save_vpx_config_surgical(vpx_mappings)

        print("\n✓ Done! Your button mappings are now active for both systems.")
    else:
        print("\n✗ Configuration not saved")

    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled by user")
        pygame.quit()
        sys.exit(0)
