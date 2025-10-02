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
    screen_number: int  # Which physical screen (0, 1, 2, etc.)
    rotation: int = 0  # 0, 90, 180, 270
    enabled: bool = True
    # Optional manual overrides - if None, auto-detect from screen_number
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    # DMD-specific display mode: "native" or "full"
    dmd_mode: str = "full"  # "native" keeps original size, "full" scales to screen


@dataclass
class DisplayConfig:
    """Display configuration for all monitors

    Each display type maps to a physical screen number.
    Resolution is auto-detected unless manually specified.
    """
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
    # Joystick button mappings (action_name -> button_number)
    joystick_buttons: Dict[str, int] = None

    def __post_init__(self):
        """Initialize default joystick buttons if None"""
        if self.joystick_buttons is None:
            self.joystick_buttons = {}


@dataclass
class AudioConfig:
    """Audio configuration"""
    table_audio: bool = True  # Play table audio when navigating to a table


class Config:
    """Main configuration class"""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._get_default_config_path()
        self.displays = DisplayConfig()
        self.vpx = VPXConfig()
        self.input = InputConfig()
        self.audio = AudioConfig()
        self.load()

    def _get_default_config_path(self) -> str:
        """Get the default configuration file path"""
        config_dir = Path.home() / ".config" / "pinballux"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "config.json")

    def _load_monitor_config(self, data: Optional[Dict[str, Any]]) -> Optional[MonitorConfig]:
        """Load a MonitorConfig from dictionary data"""
        if not data:
            return None
        return MonitorConfig(**data)

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
                        playfield=self._load_monitor_config(displays_data.get('playfield')),
                        backglass=self._load_monitor_config(displays_data.get('backglass')),
                        dmd=self._load_monitor_config(displays_data.get('dmd')),
                        fulldmd=self._load_monitor_config(displays_data.get('fulldmd')),
                        topper=self._load_monitor_config(displays_data.get('topper')),
                    )

                # Load VPX configuration
                if 'vpx' in data:
                    self.vpx = VPXConfig(**data['vpx'])

                # Load input configuration
                if 'input' in data:
                    self.input = InputConfig(**data['input'])

                # Load audio configuration
                if 'audio' in data:
                    self.audio = AudioConfig(**data['audio'])

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
                'input': asdict(self.input),
                'audio': asdict(self.audio)
            }

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

        except Exception as e:
            print(f"Error saving config: {e}")

    def _create_default_config(self) -> None:
        """Create default configuration"""
        self.displays = DisplayConfig(
            playfield=MonitorConfig("Playfield", screen_number=0, rotation=0, enabled=True),
            backglass=MonitorConfig("Backglass", screen_number=1, rotation=0, enabled=True),
            dmd=MonitorConfig("DMD", screen_number=2, rotation=0, enabled=False)
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