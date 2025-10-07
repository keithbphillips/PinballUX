#!/usr/bin/env python3
"""
Game Controller Database Manager
Manages SDL game controller mappings for VPinball
"""

from pathlib import Path
from typing import Dict, Optional
import pygame


class GameControllerManager:
    """Manages SDL game controller database for VPinball"""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize with optional custom database path"""
        if db_path is None:
            db_path = Path.home() / ".vpinball" / "gamecontrollerdb.txt"
        self.db_path = Path(db_path)

    @staticmethod
    def normalize_guid(guid: str) -> str:
        """
        Normalize GUID to standard SDL format for Linux USB devices.

        Pygame sometimes returns GUIDs with extra bytes that don't match
        the standard SDL2 format. This normalizes to the format VPinball expects.

        Standard Linux USB format: 03000000VVVVPPPPVVVV000000000000
        where VVVV = vendor ID, PPPP = product ID (little-endian)

        Args:
            guid: GUID string from pygame

        Returns:
            Normalized GUID string
        """
        if len(guid) != 32:
            return guid

        # Check if it's a USB device (starts with 03)
        if not guid.startswith('03'):
            return guid

        # Try to extract vendor and product IDs from the GUID
        # Pygame format: 0300457e790000000600000010010000
        # Standard format: 03000000790000000600000010010000
        #                    ^^ ^^^^ ^^^^      ^^^^
        #                    |  |    vendor    product
        #                    |  extra bytes
        #                    bus type

        # If bytes 4-7 are not "0000", this might be the non-standard format
        if guid[4:8] != "0000":
            # Extract what looks like vendor ID (bytes 8-11)
            # and product ID (bytes 16-19)
            vendor = guid[8:12]  # positions 8-11
            product = guid[16:20]  # positions 16-19
            version = guid[24:32]  # last 8 bytes

            # Reconstruct in standard format
            normalized = f"03000000{vendor}0000{product}0000{version}"
            print(f"Normalized GUID: {guid} -> {normalized}")
            return normalized

        return guid

    def get_joystick_info(self, joystick_index: int = 0) -> Optional[Dict[str, any]]:
        """Get information about the connected joystick"""
        try:
            if not pygame.get_init():
                pygame.init()
            pygame.joystick.init()

            if pygame.joystick.get_count() <= joystick_index:
                return None

            joy = pygame.joystick.Joystick(joystick_index)
            joy.init()

            raw_guid = joy.get_guid()
            normalized_guid = self.normalize_guid(raw_guid)

            return {
                'name': joy.get_name(),
                'guid': normalized_guid,
                'raw_guid': raw_guid,
                'num_buttons': joy.get_numbuttons(),
                'num_axes': joy.get_numaxes()
            }
        except Exception as e:
            print(f"Error getting joystick info: {e}")
            return None

    def generate_mapping_string(self, button_mappings: Dict[str, int]) -> Optional[str]:
        """
        Generate SDL mapping string from PinballUX button mappings

        VPinball has specific expectations about SDL button names:
        - leftshoulder/rightshoulder = flippers
        - start = start game
        - back = add credit
        - a = various table functions
        - x = various table functions
        - y = various table functions
        - rightstick = often used for exit
        - dpdown = often used for launch/plunger

        Args:
            button_mappings: Dict mapping action names to button numbers
                            e.g., {'LEFT_FLIPPER': 10, 'RIGHT_FLIPPER': 11, ...}

        Returns:
            SDL mapping string or None if joystick not found
        """
        joy_info = self.get_joystick_info()
        if not joy_info:
            return None

        guid = joy_info['guid']
        name = joy_info['name']

        # Map PinballUX actions to SDL button names based on VPinball's expectations
        # This mapping is based on what VPinball internally expects
        action_to_sdl = {
            'LEFT_FLIPPER': 'leftshoulder',     # VPX maps leftshoulder to left flipper
            'RIGHT_FLIPPER': 'rightshoulder',   # VPX maps rightshoulder to right flipper
            'START': 'start',                    # VPX maps start to start game
            'MENU': 'a',                         # VPX may map 'a' to add credit/menu
            'EXIT_TABLE': 'x',                   # VPX may map 'x' to exit
            'PLUNGER': 'dpdown',                 # VPX often maps dpdown to launch
            'LEFT_MAGNASAVE': 'y',               # Additional buttons
            'RIGHT_MAGNASAVE': 'back',           # VPX back button
            'SELECT': 'rightstick',              # Additional action
        }

        # Build mapping string parts
        mappings = []
        for action, sdl_button in action_to_sdl.items():
            if action in button_mappings and button_mappings[action] >= 0:
                button_num = button_mappings[action]
                # SDL format: buttonname:bN where N is the button index
                mappings.append(f"{sdl_button}:b{button_num}")

        if not mappings:
            return None

        # SDL format: GUID,Name,platform:Linux,button:bN,button2:bN,...
        mapping_str = f"{guid},{name},platform:Linux,{','.join(mappings)}"

        return mapping_str

    def write_mapping(self, mapping_string: str) -> bool:
        """
        Write or update the mapping in gamecontrollerdb.txt

        Args:
            mapping_string: Complete SDL mapping string

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract GUID from mapping string
            guid = mapping_string.split(',')[0]

            # Read existing mappings
            existing_lines = []
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    existing_lines = f.readlines()

            # Remove any existing mapping for this GUID
            filtered_lines = []
            for line in existing_lines:
                line_stripped = line.strip()
                # Keep comments and empty lines
                if not line_stripped or line_stripped.startswith('#'):
                    filtered_lines.append(line)
                # Keep mappings for other GUIDs
                elif not line_stripped.startswith(guid):
                    filtered_lines.append(line)
                # Skip existing mapping for this GUID (we'll add updated one)

            # Add the new mapping
            filtered_lines.append(f"{mapping_string}\n")

            # Write back to file
            with open(self.db_path, 'w') as f:
                f.writelines(filtered_lines)

            print(f"✓ Updated gamecontroller mapping: {self.db_path}")
            return True

        except Exception as e:
            print(f"Error writing gamecontroller mapping: {e}")
            return False

    def update_from_button_mappings(self, button_mappings: Dict[str, int]) -> bool:
        """
        Generate and write SDL mapping from PinballUX button configuration

        Args:
            button_mappings: Dict mapping action names to button numbers

        Returns:
            True if successful, False otherwise
        """
        mapping_str = self.generate_mapping_string(button_mappings)
        if not mapping_str:
            print("Could not generate mapping string (no joystick detected?)")
            return False

        return self.write_mapping(mapping_str)

    def ensure_default_mapping(self, use_reference: bool = True) -> bool:
        """
        Ensure a default gamecontroller mapping exists with correct GUID

        This uses a reference mapping that's known to work with VPinball,
        or generates one from the current button config.

        Args:
            use_reference: If True, use VPinball-compatible reference mapping

        Returns:
            True if successful, False otherwise
        """
        joy_info = self.get_joystick_info()
        if not joy_info:
            return False

        guid = joy_info['guid']
        name = joy_info['name']

        if use_reference:
            # Use a VPinball-compatible reference mapping
            # This maps common buttons to SDL names that VPinball understands
            reference_mapping = (
                f"{guid},{name},platform:Linux,"
                "leftshoulder:b10,rightshoulder:b11,start:b7,back:b8,"
                "a:b1,x:b3,y:b4,dpdown:b2,rightstick:b9"
            )
            print(f"Using VPinball-compatible reference mapping")
            return self.write_mapping(reference_mapping)
        else:
            # Generate from button config (may not work perfectly with VPinball)
            return False

    def create_default_db(self) -> bool:
        """Create a default gamecontrollerdb.txt with instructions"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            default_content = """# SDL Game Controller DB for Visual Pinball
#
# This file maps your joystick buttons to standardized gamepad buttons.
# Mappings are automatically generated by PinballUX Setup.
#
# Format: GUID,Name,platform:Linux,button:bN,...
#
# If you need to manually create a mapping:
# 1. Use AntiMicro or SDL2 Gamepad Tool
# 2. Add the mapping string below
#

"""
            with open(self.db_path, 'w') as f:
                f.write(default_content)

            return True

        except Exception as e:
            print(f"Error creating default gamecontroller db: {e}")
            return False


if __name__ == "__main__":
    """Test the game controller manager"""
    manager = GameControllerManager()

    # Get joystick info
    joy_info = manager.get_joystick_info()
    if joy_info:
        print("Detected joystick:")
        print(f"  Name: {joy_info['name']}")
        print(f"  GUID: {joy_info['guid']}")
        print(f"  Buttons: {joy_info['num_buttons']}")
        print(f"  Axes: {joy_info['num_axes']}")

        # Example button mappings
        test_mappings = {
            'LEFT_FLIPPER': 0,
            'RIGHT_FLIPPER': 1,
            'PLUNGER': 2,
            'START': 7,
            'MENU': 8,
        }

        mapping_str = manager.generate_mapping_string(test_mappings)
        print(f"\nGenerated mapping:\n{mapping_str}")

        # Uncomment to actually write:
        # manager.update_from_button_mappings(test_mappings)
    else:
        print("No joystick detected")
