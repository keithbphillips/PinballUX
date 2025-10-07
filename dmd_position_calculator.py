#!/usr/bin/env python3
"""
DMD Position Calculator
Automatically calculates optimal DMD window positioning for pinball cabinets
"""

from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class DMDConfig:
    """DMD window configuration"""
    x: int
    y: int
    width: int
    height: int

    def __str__(self):
        return f"DMD: {self.width}x{self.height} at ({self.x}, {self.y})"


class DMDPositionCalculator:
    """Calculates optimal DMD positioning for various screen configurations"""

    # Standard DMD aspect ratios
    DMD_ASPECT_RATIOS = {
        'classic': (128, 32),   # Classic 4:1 ratio (Bally/Williams)
        'wide': (192, 64),      # Wider modern DMD (3:1 ratio)
        'tall': (128, 64),      # Taller DMD (2:1 ratio)
    }

    # Default DMD sizes based on screen height
    DMD_SCALE_FACTORS = {
        1080: 3.0,  # 1080p: DMD scaled 3x
        1200: 3.5,  # 1200p: DMD scaled 3.5x
        1440: 4.0,  # 1440p: DMD scaled 4x
        2160: 6.0,  # 4K: DMD scaled 6x
    }

    def __init__(self):
        pass

    def calculate_dmd_position(
        self,
        screen_width: int,
        screen_height: int,
        dmd_type: str = 'classic',
        vertical_position: float = 0.75,
        scale_override: Optional[float] = None
    ) -> DMDConfig:
        """
        Calculate optimal DMD window position and size

        Args:
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
            dmd_type: Type of DMD ('classic', 'wide', 'tall')
            vertical_position: Where to place DMD vertically (0.0=top, 1.0=bottom)
                             Default 0.75 places it in lower quarter
            scale_override: Optional manual scale factor (overrides automatic)

        Returns:
            DMDConfig with calculated position and size
        """
        # Get base DMD dimensions
        if dmd_type not in self.DMD_ASPECT_RATIOS:
            dmd_type = 'classic'

        base_width, base_height = self.DMD_ASPECT_RATIOS[dmd_type]

        # Calculate scale factor
        if scale_override:
            scale = scale_override
        else:
            scale = self._calculate_scale_factor(screen_height)

        # Calculate DMD dimensions
        dmd_width = int(base_width * scale)
        dmd_height = int(base_height * scale)

        # Ensure DMD fits on screen with some margin
        max_width = int(screen_width * 0.9)  # 90% of screen width max
        max_height = int(screen_height * 0.25)  # 25% of screen height max

        if dmd_width > max_width:
            # Scale down to fit width
            scale_factor = max_width / dmd_width
            dmd_width = max_width
            dmd_height = int(dmd_height * scale_factor)

        if dmd_height > max_height:
            # Scale down to fit height
            scale_factor = max_height / dmd_height
            dmd_height = max_height
            dmd_width = int(dmd_width * scale_factor)

        # Calculate position - center horizontally
        dmd_x = (screen_width - dmd_width) // 2

        # Position vertically based on vertical_position parameter
        # vertical_position=0.75 means DMD center is at 75% down the screen
        dmd_center_y = int(screen_height * vertical_position)
        dmd_y = dmd_center_y - (dmd_height // 2)

        # Ensure DMD is fully on screen
        dmd_y = max(0, min(dmd_y, screen_height - dmd_height))

        return DMDConfig(
            x=dmd_x,
            y=dmd_y,
            width=dmd_width,
            height=dmd_height
        )

    def _calculate_scale_factor(self, screen_height: int) -> float:
        """
        Calculate appropriate scale factor based on screen height

        Args:
            screen_height: Screen height in pixels

        Returns:
            Scale factor for DMD
        """
        # Find closest matching resolution
        closest_height = min(
            self.DMD_SCALE_FACTORS.keys(),
            key=lambda h: abs(h - screen_height)
        )

        # Get base scale for that resolution
        base_scale = self.DMD_SCALE_FACTORS[closest_height]

        # Adjust proportionally if not exact match
        scale = base_scale * (screen_height / closest_height)

        return scale

    def calculate_for_cabinet_screens(
        self,
        dmd_screen_width: int,
        dmd_screen_height: int,
        dmd_type: str = 'classic'
    ) -> dict:
        """
        Calculate DMD positions for typical pinball cabinet screen configurations

        Args:
            dmd_screen_width: DMD display screen width
            dmd_screen_height: DMD display screen height
            dmd_type: Type of DMD aspect ratio

        Returns:
            Dict with configurations for different DMD types:
            - 'dmd': Regular PinMAME DMD (small, for ROM-based games)
            - 'fulldmd': FlexDMD (larger, for modern tables)
            - 'b2sdmd': B2S DMD (similar to fulldmd)
        """
        configs = {}

        # PinMAME DMD - smaller, lower on screen (at 80%)
        configs['dmd'] = self.calculate_dmd_position(
            dmd_screen_width,
            dmd_screen_height,
            dmd_type='classic',
            vertical_position=0.80,
            scale_override=None  # Auto-scale
        )

        # FlexDMD/FullDMD - larger, centered in lower portion (at 70%)
        configs['fulldmd'] = self.calculate_dmd_position(
            dmd_screen_width,
            dmd_screen_height,
            dmd_type=dmd_type,
            vertical_position=0.70,
            scale_override=None  # Auto-scale, will be bigger
        )

        # B2S DMD - same as fulldmd
        configs['b2sdmd'] = configs['fulldmd']

        return configs

    def calculate_native_dmd_size(
        self,
        dmd_type: str = 'classic',
        scale: float = 3.0
    ) -> Tuple[int, int]:
        """
        Calculate DMD size without position (for native size mode)

        Args:
            dmd_type: Type of DMD aspect ratio
            scale: Scale factor

        Returns:
            Tuple of (width, height)
        """
        if dmd_type not in self.DMD_ASPECT_RATIOS:
            dmd_type = 'classic'

        base_width, base_height = self.DMD_ASPECT_RATIOS[dmd_type]

        return (
            int(base_width * scale),
            int(base_height * scale)
        )


def main():
    """Test the DMD position calculator"""
    calc = DMDPositionCalculator()

    # Test with common screen resolutions
    test_configs = [
        (1920, 1080, "1080p Landscape"),
        (1080, 1920, "1080p Portrait"),
        (1920, 1200, "1920x1200"),
        (2560, 1440, "1440p"),
        (3840, 2160, "4K"),
    ]

    print("DMD Position Calculator Test")
    print("=" * 70)

    for width, height, label in test_configs:
        print(f"\n{label} ({width}x{height}):")
        print("-" * 70)

        # Calculate for different DMD types
        for dmd_type in ['classic', 'wide', 'tall']:
            config = calc.calculate_dmd_position(
                width, height, dmd_type=dmd_type
            )
            print(f"  {dmd_type:8s}: {config}")

        # Calculate cabinet configuration
        print(f"\n  Cabinet configs:")
        cabinet_configs = calc.calculate_for_cabinet_screens(width, height)
        for name, cfg in cabinet_configs.items():
            print(f"    {name:10s}: {cfg}")

    print("\n" + "=" * 70)
    print("Test complete!")


if __name__ == "__main__":
    main()
