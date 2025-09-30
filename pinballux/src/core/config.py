"""
Configuration management for PinballUX
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class MonitorConfig:
    """Configuration for a single monitor"""
    name: str
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080
    rotation: int = 0  # 0, 90, 180, 270
    enabled: bool = True


@dataclass
class DisplayConfig:
    """Display configuration for all monitors"""
    playfield: Optional[MonitorConfig] = None
    backglass: Optional[MonitorConfig] = None
    dmd: Optional[MonitorConfig] = None
    fulldmd: Optional[MonitorConfig] = None
    topper: Optional[MonitorConfig] = None


@dataclass
class VPXConfig:
    """Visual Pinball configuration"""
    executable_path: str = ""
    table_directory: str = ""
    media_directory: str = ""
    use_standalone: bool = True


@dataclass
class InputConfig:
    """Input configuration"""
    keyboard_enabled: bool = True
    joystick_enabled: bool = True
    exit_key: str = "Escape"
    select_key: str = "Return"
    up_key: str = "Up"
    down_key: str = "Down"
    left_key: str = "Left"
    right_key: str = "Right"


class Config:
    """Main configuration class"""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._get_default_config_path()
        self.displays = DisplayConfig()
        self.vpx = VPXConfig()
        self.input = InputConfig()
        self.load()

    def _get_default_config_path(self) -> str:
        """Get the default configuration file path"""
        config_dir = Path.home() / ".config" / "pinballux"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "config.json")

    def load(self) -> None:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)

                # Load display configuration
                if 'displays' in data:
                    displays_data = data['displays']
                    self.displays = DisplayConfig(
                        playfield=MonitorConfig(**displays_data.get('playfield', {})) if displays_data.get('playfield') else None,
                        backglass=MonitorConfig(**displays_data.get('backglass', {})) if displays_data.get('backglass') else None,
                        dmd=MonitorConfig(**displays_data.get('dmd', {})) if displays_data.get('dmd') else None,
                        fulldmd=MonitorConfig(**displays_data.get('fulldmd', {})) if displays_data.get('fulldmd') else None,
                        topper=MonitorConfig(**displays_data.get('topper', {})) if displays_data.get('topper') else None,
                    )

                # Load VPX configuration
                if 'vpx' in data:
                    self.vpx = VPXConfig(**data['vpx'])

                # Load input configuration
                if 'input' in data:
                    self.input = InputConfig(**data['input'])

                # Update paths to use project-relative paths if they're still using old defaults
                self._update_default_paths()

            except Exception as e:
                print(f"Error loading config: {e}")
                self._create_default_config()
        else:
            self._create_default_config()

    def _update_default_paths(self):
        """Update paths to use project-relative directories"""
        project_root = Path(__file__).parents[3]  # Go up from src/core/config.py to project root

        new_executable_path = str(project_root / "vpinball" / "VPinballX_GL")
        new_table_dir = str(project_root / "pinballux" / "data" / "tables")
        new_media_dir = str(project_root / "pinballux" / "data" / "media")

        # Update executable path if empty or pointing to old locations
        if not self.vpx.executable_path or "vpinball_standalone" in self.vpx.executable_path or "VPinballX_GL" in self.vpx.executable_path:
            self.vpx.executable_path = new_executable_path

        # Update paths if they're still using old defaults or are empty
        if not self.vpx.table_directory or self.vpx.table_directory.endswith("VPX/Tables"):
            self.vpx.table_directory = new_table_dir

        if not self.vpx.media_directory or self.vpx.media_directory.endswith("VPX/Media"):
            self.vpx.media_directory = new_media_dir

    def save(self) -> None:
        """Save configuration to file"""
        try:
            config_data = {
                'displays': {
                    'playfield': asdict(self.displays.playfield) if self.displays.playfield else None,
                    'backglass': asdict(self.displays.backglass) if self.displays.backglass else None,
                    'dmd': asdict(self.displays.dmd) if self.displays.dmd else None,
                    'fulldmd': asdict(self.displays.fulldmd) if self.displays.fulldmd else None,
                    'topper': asdict(self.displays.topper) if self.displays.topper else None,
                },
                'vpx': asdict(self.vpx),
                'input': asdict(self.input)
            }

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

        except Exception as e:
            print(f"Error saving config: {e}")

    def _create_default_config(self) -> None:
        """Create default configuration"""
        self.displays = DisplayConfig(
            playfield=MonitorConfig("Playfield", 0, 0, 1920, 1080),
            backglass=MonitorConfig("Backglass", 1920, 0, 1920, 1080),
            dmd=MonitorConfig("DMD", 0, 1080, 512, 128)
        )

        # Get project root directory
        project_root = Path(__file__).parents[3]  # Go up from src/core/config.py to project root

        self.vpx = VPXConfig(
            executable_path=str(project_root / "vpinball" / "VPinballX_GL"),
            table_directory=str(project_root / "pinballux" / "data" / "tables"),
            media_directory=str(project_root / "pinballux" / "data" / "media")
        )

        self.input = InputConfig()
        self.save()