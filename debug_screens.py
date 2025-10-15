#!/usr/bin/env python3
"""
Debug script to check what screens are detected and what DMD positioning calculates
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dmd_position_calculator import DMDPositionCalculator

def main():
    print("=" * 70)
    print("Screen Detection Debug")
    print("=" * 70)

    # Try to detect screens using PyQt6
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        screens = []

        print("\nDetected Screens (via PyQt6):")
        print("-" * 70)

        for i, screen in enumerate(app.screens()):
            geometry = screen.geometry()
            screen_info = {
                'index': i,
                'name': screen.name(),
                'width': geometry.width(),
                'height': geometry.height(),
                'x': geometry.x(),
                'y': geometry.y()
            }
            screens.append(screen_info)

            print(f"\nScreen {i}: {screen.name()}")
            print(f"  Position: ({geometry.x()}, {geometry.y()})")
            print(f"  Size: {geometry.width()}x{geometry.height()}")

            # Calculate DMD positions for this screen
            calc = DMDPositionCalculator()
            configs = calc.calculate_for_cabinet_screens(geometry.width(), geometry.height())

            print(f"  FullDMD for this screen:")
            fulldmd = configs['fulldmd']
            print(f"    Relative: ({fulldmd.x}, {fulldmd.y}) {fulldmd.width}x{fulldmd.height}")
            print(f"    Absolute: ({geometry.x() + fulldmd.x}, {geometry.y() + fulldmd.y}) {fulldmd.width}x{fulldmd.height}")

        print("\n" + "=" * 70)
        print("Check VPinballX.ini FlexDMD settings and compare")
        print("=" * 70)

    except Exception as e:
        print(f"Error detecting screens: {e}")
        print("\nManual calculation for 3840x2160:")
        calc = DMDPositionCalculator()
        configs = calc.calculate_for_cabinet_screens(3840, 2160)
        fulldmd = configs['fulldmd']
        print(f"  Relative: ({fulldmd.x}, {fulldmd.y}) {fulldmd.width}x{fulldmd.height}")
        print(f"  If screen at x=3840: Absolute ({3840 + fulldmd.x}, {fulldmd.y}) {fulldmd.width}x{fulldmd.height}")

if __name__ == "__main__":
    main()
