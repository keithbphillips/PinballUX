#!/usr/bin/env python3
"""
PinballUX Setup GUI
Configuration tool for PinballUX with display, input, and VPX settings
"""

import sys
import os
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import zipfile
import tarfile
import shutil

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QFileDialog, QMessageBox,
    QComboBox, QListWidget, QListWidgetItem, QScrollArea, QProgressBar,
    QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Handle both development and installed import paths
try:
    from pinballux.src.core.config import Config, MonitorConfig
except ModuleNotFoundError:
    from src.core.config import Config, MonitorConfig
import pygame
import shutil
from datetime import datetime
import configparser

# Import the gamecontroller manager
try:
    from gamecontroller_manager import GameControllerManager
except ImportError:
    # If not in Python path, try relative import
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from gamecontroller_manager import GameControllerManager


def setup_vpinmame_roms_symlink():
    """Ensure ~/.pinmame/roms points at the project's data/roms directory.

    VPinMAME loads ROMs from ~/.pinmame/roms; the project keeps them under
    pinballux/data/roms. This mirrors the symlink setup done by the frontend
    (pinballux/src/main.py) so the link is in place after running setup too.
    """
    roms_dir = Path(project_root) / "pinballux" / "data" / "roms"

    try:
        roms_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass

    vpinmame_dir = Path.home() / ".pinmame"
    vpinmame_roms = vpinmame_dir / "roms"
    vpinmame_dir.mkdir(parents=True, exist_ok=True)

    if vpinmame_roms.is_symlink():
        if vpinmame_roms.resolve() == roms_dir.resolve():
            return  # Already correct
        vpinmame_roms.unlink()  # Wrong target - replace it
    elif vpinmame_roms.exists():
        # A real directory/file is in the way; don't clobber user data
        print(f"Warning: {vpinmame_roms} exists and is not a symlink; "
              f"remove or rename it so the roms symlink can be created.")
        return

    try:
        vpinmame_roms.symlink_to(roms_dir, target_is_directory=True)
    except Exception as e:
        print(f"Failed to create VPinMAME roms symlink: {e}")


def path_inside_roms(path_str):
    """If `path_str` is at or inside a ROMs folder, return that ROMs dir; else None.

    The Table/Media directories must never point inside the ROMs folder. When
    they do, media downloaded by the Table Manager gets written in among the
    .zip ROM files (the audio/ images/ videos/ subfolder mess), and relocating
    it later breaks the database's stored media paths. We resolve symlinks so
    both the project's data/roms and the ~/.pinmame/roms link are caught.
    """
    if not path_str or not path_str.strip():
        return None
    roms_candidates = [
        Path(project_root) / "pinballux" / "data" / "roms",
        Path.home() / ".pinmame" / "roms",
    ]
    target = os.path.realpath(path_str.strip())
    for cand in roms_candidates:
        try:
            roms = os.path.realpath(cand)
        except Exception:
            continue
        if target == roms or target.startswith(roms + os.sep):
            return roms
    return None


class VPXIniManager:
    """Manager for reading/writing VPinballX.ini files"""

    def __init__(self, ini_path: Optional[Path] = None):
        """Initialize with optional custom ini path"""
        if ini_path is None:
            # Default VPX path
            ini_path = Path.home() / ".vpinball" / "VPinballX.ini"
        self.ini_path = Path(ini_path)

    def read_display_config(self, display_type: str) -> Dict[str, any]:
        """Read display configuration from VPinballX.ini"""
        if not self.ini_path.exists():
            return {}

        try:
            with open(self.ini_path, 'r') as f:
                lines = f.readlines()

            config = {}

            # Map display types to VPX ini keys
            key_mapping = {
                'playfield': {
                    'x': 'WindowPosX',
                    'y': 'WindowPosY',
                    'width': 'Width',
                    'height': 'Height'
                },
                'backglass': {
                    'x': 'B2SBackglassX',
                    'y': 'B2SBackglassY',
                    'width': 'B2SBackglassWidth',
                    'height': 'B2SBackglassHeight',
                    'rotation': 'B2SBackglassRotation'
                },
                'dmd': {
                    'x': 'PinMAMEWindowX',
                    'y': 'PinMAMEWindowY',
                    'width': 'PinMAMEWindowWidth',
                    'height': 'PinMAMEWindowHeight',
                    'rotation': 'PinMAMEWindowRotation'
                },
                'fulldmd': {
                    'x': 'FlexDMDWindowX',
                    'y': 'FlexDMDWindowY',
                    'width': 'FlexDMDWindowWidth',
                    'height': 'FlexDMDWindowHeight',
                    'rotation': 'FlexDMDWindowRotation'
                },
                'b2sdmd': {
                    'x': 'B2SDMDX',
                    'y': 'B2SDMDY',
                    'width': 'B2SDMDWidth',
                    'height': 'B2SDMDHeight',
                    'rotation': 'B2SDMDRotation'
                }
            }

            if display_type not in key_mapping:
                return {}

            keys = key_mapping[display_type]

            # Parse the file line by line
            for line in lines:
                line = line.strip()
                if '=' in line and not line.startswith(';'):
                    key_part = line.split('=')[0].strip()
                    value_part = line.split('=', 1)[1].strip()

                    for config_key, ini_key in keys.items():
                        if key_part == ini_key and value_part:
                            try:
                                config[config_key] = int(value_part)
                            except ValueError:
                                config[config_key] = value_part

            return config

        except Exception as e:
            print(f"Error reading VPinballX.ini: {e}")
            return {}

    def write_display_config(self, display_type: str, config: Dict[str, any]) -> bool:
        """Write display configuration to VPinballX.ini"""
        if not self.ini_path.exists():
            return False

        # Map display types to VPX ini keys
        key_mapping = {
            'playfield': {
                'x': 'WindowPosX',
                'y': 'WindowPosY',
                'width': 'Width',
                'height': 'Height'
            },
            'backglass': {
                'x': 'B2SBackglassX',
                'y': 'B2SBackglassY',
                'width': 'B2SBackglassWidth',
                'height': 'B2SBackglassHeight',
                'rotation': 'B2SBackglassRotation'
            },
            'dmd': {
                'x': 'PinMAMEWindowX',
                'y': 'PinMAMEWindowY',
                'width': 'PinMAMEWindowWidth',
                'height': 'PinMAMEWindowHeight',
                'rotation': 'PinMAMEWindowRotation'
            },
            'fulldmd': {
                'x': 'FlexDMDWindowX',
                'y': 'FlexDMDWindowY',
                'width': 'FlexDMDWindowWidth',
                'height': 'FlexDMDWindowHeight',
                'rotation': 'FlexDMDWindowRotation'
            },
            'b2sdmd': {
                'x': 'B2SDMDX',
                'y': 'B2SDMDY',
                'width': 'B2SDMDWidth',
                'height': 'B2SDMDHeight',
                'rotation': 'B2SDMDRotation'
            }
        }

        if display_type not in key_mapping:
            return False

        try:
            # Create backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.ini_path.parent / f"VPinballX.ini.backup_{timestamp}"
            shutil.copy2(self.ini_path, backup_path)

            # Read the file
            with open(self.ini_path, 'r') as f:
                lines = f.readlines()

            keys = key_mapping[display_type]
            updated_keys = set()

            # Update existing lines
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if '=' in line_stripped and not line_stripped.startswith(';'):
                    key_part = line_stripped.split('=')[0].strip()

                    for config_key, ini_key in keys.items():
                        if key_part == ini_key and config_key in config:
                            value = config[config_key]
                            if value is not None and str(value).strip():
                                lines[i] = f"{ini_key} = {value}\n"
                                updated_keys.add(ini_key)
                            break

            # Add missing keys to [Standalone] section
            missing_keys = set(keys.values()) - updated_keys
            if missing_keys:
                # Find [Standalone] section
                standalone_idx = None
                next_section_idx = None

                for i, line in enumerate(lines):
                    if line.strip() == '[Standalone]':
                        standalone_idx = i
                    elif standalone_idx is not None and line.strip().startswith('['):
                        next_section_idx = i
                        break

                if standalone_idx is not None:
                    insert_idx = next_section_idx if next_section_idx else len(lines)

                    for config_key, ini_key in keys.items():
                        if ini_key in missing_keys and config_key in config:
                            value = config[config_key]
                            if value is not None and str(value).strip():
                                lines.insert(insert_idx, f"{ini_key} = {value}\n")

            # Write back
            with open(self.ini_path, 'w') as f:
                f.writelines(lines)

            return True

        except Exception as e:
            print(f"Error writing VPinballX.ini: {e}")
            return False

    def read_joystick_config(self) -> Dict[str, int]:
        """Read joystick button mappings from VPinballX.ini"""
        if not self.ini_path.exists():
            return {}

        try:
            with open(self.ini_path, 'r') as f:
                lines = f.readlines()

            # Map VPX ini keys to PinballUX actions
            vpx_to_ux_mapping = {
                'JoyLFlipKey': 'LEFT_FLIPPER',
                'JoyRFlipKey': 'RIGHT_FLIPPER',
                'JoyPlungerKey': 'PLUNGER',
                'JoyStartGameKey': 'START',
                'JoyAddCreditKey': 'MENU',
                'JoyLMagnaSave': 'LEFT_MAGNASAVE',
                'JoyRMagnaSave': 'RIGHT_MAGNASAVE',
                'JoyExitGameKey': 'EXIT_TABLE',
            }

            config = {}

            # Parse the file
            for line in lines:
                line = line.strip()
                if '=' in line and not line.startswith(';'):
                    key_part = line.split('=')[0].strip()
                    value_part = line.split('=', 1)[1].strip()

                    if key_part in vpx_to_ux_mapping and value_part:
                        try:
                            button_num = int(value_part)
                            ux_action = vpx_to_ux_mapping[key_part]
                            config[ux_action] = button_num
                        except ValueError:
                            pass

            return config

        except Exception as e:
            print(f"Error reading joystick config from VPinballX.ini: {e}")
            return {}

    def read_bgset(self) -> int:
        """Read BGSet value from VPinballX.ini

        Returns:
            0 for Desktop mode, 1 for Cabinet mode
        """
        if not self.ini_path.exists():
            return 0  # Default to Desktop

        try:
            with open(self.ini_path, 'r') as f:
                lines = f.readlines()

            # Parse the file
            for line in lines:
                line = line.strip()
                if '=' in line and not line.startswith(';'):
                    key_part = line.split('=')[0].strip()
                    value_part = line.split('=', 1)[1].strip()

                    if key_part == 'BGSet' and value_part:
                        try:
                            return int(value_part)
                        except ValueError:
                            return 0

            return 0  # Default to Desktop if not found

        except Exception as e:
            print(f"Error reading BGSet from VPinballX.ini: {e}")
            return 0

    def write_bgset(self, bgset: int) -> bool:
        """Write BGSet value to VPinballX.ini

        Args:
            bgset: 0 for Desktop mode, 1 for Cabinet mode

        Returns:
            True if successful, False otherwise
        """
        if not self.ini_path.exists():
            return False

        try:
            # Create backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.ini_path.parent / f"VPinballX.ini.backup_{timestamp}"
            shutil.copy2(self.ini_path, backup_path)

            # Read the file
            with open(self.ini_path, 'r') as f:
                lines = f.readlines()

            # Track if we updated an existing line
            updated = False

            # Update existing BGSet line
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if '=' in line_stripped and not line_stripped.startswith(';'):
                    key_part = line_stripped.split('=')[0].strip()

                    if key_part == 'BGSet':
                        lines[i] = f"BGSet = {bgset}\n"
                        updated = True
                        break

            # If BGSet doesn't exist, add it to [Standalone] section
            if not updated:
                standalone_idx = None
                next_section_idx = None

                for i, line in enumerate(lines):
                    if line.strip() == '[Standalone]':
                        standalone_idx = i
                    elif standalone_idx is not None and line.strip().startswith('['):
                        next_section_idx = i
                        break

                if standalone_idx is not None:
                    insert_idx = next_section_idx if next_section_idx else len(lines)
                    lines.insert(insert_idx, f"BGSet = {bgset}\n")

            # Write back
            with open(self.ini_path, 'w') as f:
                f.writelines(lines)

            return True

        except Exception as e:
            print(f"Error writing BGSet to VPinballX.ini: {e}")
            return False

    def read_aa_factor(self) -> float:
        """Read AAFactor (render/texture scaling) from [Player]. Default 0.85."""
        default = 0.85
        if not self.ini_path.exists():
            return default

        try:
            with open(self.ini_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith(';'):
                        key_part = line.split('=')[0].strip()
                        value_part = line.split('=', 1)[1].strip()
                        if key_part == 'AAFactor' and value_part:
                            return float(value_part)
        except Exception as e:
            print(f"Error reading AAFactor from VPinballX.ini: {e}")

        return default

    def write_aa_factor(self, value: float) -> bool:
        """Write AAFactor (render/texture scaling) to the [Player] section."""
        return self._write_key('Player', 'AAFactor', value)

    def _write_key(self, section: str, key: str, value) -> bool:
        """Update (or insert) a single key within the given .ini section."""
        if not self.ini_path.exists():
            return False

        try:
            # Create backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.ini_path.parent / f"VPinballX.ini.backup_{timestamp}"
            shutil.copy2(self.ini_path, backup_path)

            with open(self.ini_path, 'r') as f:
                lines = f.readlines()

            in_section = False
            section_idx = None
            next_section_idx = None
            updated = False

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('[') and stripped.endswith(']'):
                    if stripped == f'[{section}]':
                        in_section = True
                        section_idx = i
                    elif in_section:
                        next_section_idx = i
                        break
                    else:
                        in_section = False
                elif in_section and '=' in stripped and not stripped.startswith(';'):
                    if stripped.split('=')[0].strip() == key:
                        lines[i] = f"{key} = {value}\n"
                        updated = True
                        break

            # Key not present in the section yet - insert it
            if not updated and section_idx is not None:
                insert_idx = next_section_idx if next_section_idx else len(lines)
                lines.insert(insert_idx, f"{key} = {value}\n")
                updated = True

            if updated:
                with open(self.ini_path, 'w') as f:
                    f.writelines(lines)

            return updated

        except Exception as e:
            print(f"Error writing {key} to VPinballX.ini: {e}")
            return False


class KeyCaptureButton(QPushButton):
    """Button that captures keyboard input"""

    def __init__(self, current_key: str = ""):
        super().__init__(current_key or "Click to set key")
        self.current_key = current_key
        self.capturing = False
        self.clicked.connect(self.start_capture)

    def start_capture(self):
        """Start capturing key presses"""
        self.capturing = True
        self.setText("Press a key...")
        self.setStyleSheet("background-color: #ffeb3b;")

    def keyPressEvent(self, event):
        """Capture key press"""
        if self.capturing:
            # Use text() to get the actual key name which includes left/right modifiers
            key_text = event.text()

            # For modifier keys and special keys, use the key name
            if not key_text or event.key() in [Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt,
                                                Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                                                Qt.Key.Key_Tab, Qt.Key.Key_Space, Qt.Key.Key_Backspace,
                                                Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down]:
                # Get native scan code to differentiate left/right modifiers
                scan_code = event.nativeScanCode()

                # Map native scan codes for left/right shift (Linux X11)
                if event.key() == Qt.Key.Key_Shift:
                    if scan_code == 50:  # Left Shift
                        key = "Shift_L"
                    elif scan_code == 62:  # Right Shift
                        key = "Shift_R"
                    else:
                        key = "Shift"
                elif event.key() == Qt.Key.Key_Control:
                    if scan_code == 37:  # Left Control
                        key = "Control_L"
                    elif scan_code == 105:  # Right Control
                        key = "Control_R"
                    else:
                        key = "Control"
                elif event.key() == Qt.Key.Key_Alt:
                    if scan_code == 64:  # Left Alt
                        key = "Alt_L"
                    elif scan_code == 108:  # Right Alt
                        key = "Alt_R"
                    else:
                        key = "Alt"
                else:
                    key = QKeySequence(event.key()).toString()
            else:
                key = key_text

            self.current_key = key
            self.setText(key)
            self.capturing = False
            self.setStyleSheet("")
        else:
            super().keyPressEvent(event)


class JoystickButton(QPushButton):
    """Button that captures joystick button presses"""

    def __init__(self, action_name: str, current_button: int = -1):
        super().__init__(f"Button {current_button}" if current_button >= 0 else "Click to set")
        self.action_name = action_name
        self.current_button = current_button
        self.capturing = False
        self.joystick = None

        # Initialize pygame for joystick
        try:
            if not pygame.get_init():
                pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
        except:
            pass

        self.clicked.connect(self.start_capture)

        # Timer for checking joystick input
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_joystick)

    def start_capture(self):
        """Start capturing joystick button presses"""
        if not self.joystick:
            QMessageBox.warning(self, "No Joystick", "No joystick detected. Please connect a joystick.")
            return

        self.capturing = True
        self.setText("Press a button...")
        self.setStyleSheet("background-color: #ffeb3b;")
        self.timer.start(50)  # Check every 50ms

    def check_joystick(self):
        """Check for joystick button presses"""
        if not self.capturing or not self.joystick:
            return

        pygame.event.pump()

        # Check all buttons
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i):
                self.current_button = i
                self.setText(f"Button {i}")
                self.capturing = False
                self.setStyleSheet("")
                self.timer.stop()
                break

    def get_button(self) -> int:
        """Get the current button number"""
        return self.current_button


class DisplayConfigTab(QWidget):
    """Display settings for the Raspberry Pi cabinet.

    The Pi cabinet has a fixed two-screen 1080p layout (playfield on screen 0,
    backglass on screen 1), so the only adjustable display setting is where the
    VPinball DMD window sits over the backglass on the second screen. Also
    exposes the VPinball render scale (AAFactor) for performance tuning.
    """

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.vpx_manager = VPXIniManager()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # --- DMD position over the backglass (second screen) ---
        dmd_group = QGroupBox("DMD Position (Backglass Screen)")
        dmd_layout = QFormLayout()

        # Prefer the live VPinballX.ini DMD window values, fall back to the
        # PinballUX config, then to sensible defaults.
        vpx_dmd = self.vpx_manager.read_display_config('dmd')
        current = self.config.displays.dmd

        def _initial(key, attr, default):
            if key in vpx_dmd:
                return vpx_dmd[key]
            if current is not None and getattr(current, attr) is not None:
                return getattr(current, attr)
            return default

        self.dmd_x = QSpinBox()
        self.dmd_x.setRange(-10000, 10000)
        self.dmd_x.setValue(_initial('x', 'x', 2368))
        dmd_layout.addRow("X Position:", self.dmd_x)

        self.dmd_y = QSpinBox()
        self.dmd_y.setRange(-10000, 10000)
        self.dmd_y.setValue(_initial('y', 'y', 824))
        dmd_layout.addRow("Y Position:", self.dmd_y)

        self.dmd_width = QSpinBox()
        self.dmd_width.setRange(0, 10000)
        self.dmd_width.setValue(_initial('width', 'width', 1024))
        dmd_layout.addRow("Width:", self.dmd_width)

        self.dmd_height = QSpinBox()
        self.dmd_height.setRange(0, 10000)
        self.dmd_height.setValue(_initial('height', 'height', 256))
        dmd_layout.addRow("Height:", self.dmd_height)

        dmd_info = QLabel(
            "Position the VPinball DMD window over the backglass on the second "
            "screen.\nX/Y are absolute desktop coordinates; the second screen "
            "starts at X = 1920."
        )
        dmd_info.setStyleSheet("color: #666; font-size: 11px;")
        dmd_info.setWordWrap(True)
        dmd_layout.addRow(dmd_info)

        dmd_group.setLayout(dmd_layout)
        layout.addWidget(dmd_group)

        # --- Render performance ---
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout()

        self.aa_factor = QDoubleSpinBox()
        self.aa_factor.setRange(0.10, 2.00)
        self.aa_factor.setSingleStep(0.05)
        self.aa_factor.setDecimals(2)
        self.aa_factor.setValue(self.vpx_manager.read_aa_factor())
        perf_layout.addRow("Screen Texture Scaling (AAFactor):", self.aa_factor)

        perf_info = QLabel(
            "VPinball render scale. Lower values improve performance, higher "
            "values look sharper. Default 0.85."
        )
        perf_info.setStyleSheet("color: #666; font-size: 11px;")
        perf_info.setWordWrap(True)
        perf_layout.addRow(perf_info)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        layout.addStretch()
        self.setLayout(layout)

    def save_config(self):
        """Save DMD position and render scale to PinballUX config + VPinballX.ini"""
        x = self.dmd_x.value()
        y = self.dmd_y.value()
        width = self.dmd_width.value()
        height = self.dmd_height.value()

        # Update the PinballUX DMD media window so the frontend preview matches
        # where VPinball will draw the DMD during play (second screen / screen 1).
        self.config.displays.dmd = MonitorConfig(
            name="Dmd",
            screen_number=1,
            rotation=0,
            enabled=True,
            x=x,
            y=y,
            width=width,
            height=height,
            dmd_mode="full"
        )

        # Write the DMD window position to VPinballX.ini. Mirror to the B2S DMD
        # so tables using either the PinMAME or B2S DMD land in the same spot.
        dmd_config = {'x': x, 'y': y, 'width': width, 'height': height}
        self.vpx_manager.write_display_config('dmd', dmd_config)
        self.vpx_manager.write_display_config('b2sdmd', dmd_config)

        # Write the render scale (AAFactor)
        self.vpx_manager.write_aa_factor(self.aa_factor.value())


class VPinballDownloadThread(QThread):
    """Thread for downloading and extracting VPinball"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, url: str, dest_dir: Path):
        super().__init__()
        self.url = url
        self.dest_dir = dest_dir

    def run(self):
        try:
            # Create destination directory
            self.dest_dir.mkdir(parents=True, exist_ok=True)

            # Download file
            zip_path = self.dest_dir / "vpinball.zip"
            self.progress.emit("Downloading VPinball...")

            def report_hook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int((block_num * block_size / total_size) * 100)
                    self.progress.emit(f"Downloading: {percent}%")

            urllib.request.urlretrieve(self.url, zip_path, reporthook=report_hook)
            self.progress.emit("Download complete!")

            # Extract zip
            self.progress.emit("Extracting zip file...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.dest_dir)
            self.progress.emit("Zip extracted!")

            # Find and extract tar file (check for various tar formats)
            tar_patterns = ["*.tar", "*.tar.gz", "*.tar.bz2", "*.tgz"]
            tar_path = None
            for pattern in tar_patterns:
                tar_files = list(self.dest_dir.glob(pattern))
                if tar_files:
                    tar_path = tar_files[0]
                    break

            if tar_path:
                self.progress.emit(f"Found tar file: {tar_path.name}")
                self.progress.emit(f"Extracting to {self.dest_dir}...")
                with tarfile.open(tar_path, 'r:*') as tar_ref:
                    tar_ref.extractall(self.dest_dir)
                self.progress.emit("Tar extracted!")

                # Clean up tar file
                tar_path.unlink()
                self.progress.emit(f"Cleaned up {tar_path.name}")
            else:
                self.progress.emit("No tar file found in zip")

            # Clean up zip file
            zip_path.unlink()
            self.progress.emit("Cleaned up zip file")

            self.finished.emit(True, f"✓ VPinball installed successfully to {self.dest_dir}")

        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")


class VPXConfigTab(QWidget):
    """Tab for VPX configuration"""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.vpx_manager = VPXIniManager()
        self.download_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # VPX Mode (Desktop vs Cabinet)
        mode_group = QGroupBox("VPinball Mode")
        mode_layout = QVBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Desktop View (BGSet=0)", 0)
        self.mode_combo.addItem("Cabinet Mode (BGSet=1)", 1)

        # Read current BGSet value from VPinballX.ini
        current_bgset = self.vpx_manager.read_bgset()
        self.mode_combo.setCurrentIndex(current_bgset)

        mode_layout.addWidget(QLabel("Display Mode:"))
        mode_layout.addWidget(self.mode_combo)

        mode_info = QLabel(
            "• Desktop View: Single playfield display only\n"
            "• Cabinet Mode: Multi-screen pinball cabinet setup"
        )
        mode_info.setStyleSheet("color: #666; font-size: 11px;")
        mode_layout.addWidget(mode_info)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # VPX Executable
        exe_group = QGroupBox("Visual Pinball Executable")
        exe_layout = QHBoxLayout()
        self.exe_path = QLineEdit(self.config.vpx.executable_path)
        exe_layout.addWidget(self.exe_path)
        browse_exe = QPushButton("Browse...")
        browse_exe.clicked.connect(self.browse_executable)
        exe_layout.addWidget(browse_exe)
        exe_group.setLayout(exe_layout)
        layout.addWidget(exe_group)

        # Table Directory
        table_group = QGroupBox("Table Directory")
        table_layout = QHBoxLayout()
        self.table_dir = QLineEdit(self.config.vpx.table_directory)
        table_layout.addWidget(self.table_dir)
        browse_table = QPushButton("Browse...")
        browse_table.clicked.connect(self.browse_table_dir)
        table_layout.addWidget(browse_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Media Directory
        media_group = QGroupBox("Media Directory")
        media_layout = QHBoxLayout()
        self.media_dir = QLineEdit(self.config.vpx.media_directory)
        media_layout.addWidget(self.media_dir)
        browse_media = QPushButton("Browse...")
        browse_media.clicked.connect(self.browse_media_dir)
        media_layout.addWidget(browse_media)
        media_group.setLayout(media_layout)
        layout.addWidget(media_group)

        # VPinball Download
        download_group = QGroupBox("Download VPinball")
        download_layout = QVBoxLayout()

        # URL field
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Download URL:"))
        self.vpinball_url = QLineEdit(
            "https://github.com/vpinball/vpinball/releases/download/v10.8.0-2051-28dd6c3/VPinballX_GL-10.8.0-2052-5a81d4e-Release-linux-aarch64-rpi.zip"
        )
        url_layout.addWidget(self.vpinball_url)
        download_layout.addLayout(url_layout)

        # Download button
        button_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download and Install")
        self.download_btn.clicked.connect(self.download_vpinball)
        button_layout.addWidget(self.download_btn)
        button_layout.addStretch()
        download_layout.addLayout(button_layout)

        # Progress log
        self.download_log = QTextEdit()
        self.download_log.setMaximumHeight(100)
        self.download_log.setReadOnly(True)
        download_layout.addWidget(self.download_log)

        download_group.setLayout(download_layout)
        layout.addWidget(download_group)

        layout.addStretch()
        self.setLayout(layout)

    def browse_executable(self):
        """Browse for VPX executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Visual Pinball Executable",
            str(Path(self.exe_path.text()).parent) if self.exe_path.text() else "",
            "Executable Files (*)"
        )
        if file_path:
            self.exe_path.setText(file_path)

    def browse_table_dir(self):
        """Browse for table directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Table Directory",
            self.table_dir.text() or ""
        )
        if dir_path:
            self.table_dir.setText(dir_path)

    def browse_media_dir(self):
        """Browse for media directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Media Directory",
            self.media_dir.text() or ""
        )
        if dir_path:
            self.media_dir.setText(dir_path)

    def download_vpinball(self):
        """Download and install VPinball"""
        url = self.vpinball_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a download URL")
            return

        # Destination directory
        dest_dir = Path.home() / "VPinballX"

        # Confirm download
        reply = QMessageBox.question(
            self,
            "Download VPinball",
            f"This will download and install VPinball to:\n{dest_dir}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Start download
        self.download_log.clear()
        self.download_log.append("Starting download...")
        self.download_btn.setEnabled(False)

        self.download_thread = VPinballDownloadThread(url, dest_dir)
        self.download_thread.progress.connect(self.on_download_progress)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def on_download_progress(self, message: str):
        """Handle download progress"""
        self.download_log.append(message)

    def on_download_finished(self, success: bool, message: str):
        """Handle download completion"""
        self.download_btn.setEnabled(True)
        self.download_log.append(message)

        if success:
            # Update executable path to the downloaded binary
            dest_dir = Path.home() / "VPinballX"
            exe_path = dest_dir / "VPinballX_GL"
            if exe_path.exists():
                self.exe_path.setText(str(exe_path))
                self.download_log.append(f"Executable path updated to: {exe_path}")

                # Execute VPinballX_GL to create initial VPinballX.ini
                self.download_log.append("Creating initial VPinballX.ini configuration...")
                try:
                    import subprocess
                    # Run VPinballX_GL with no arguments to initialize config
                    # It should exit quickly and create the default ini file
                    result = subprocess.run(
                        [str(exe_path)],
                        timeout=5,
                        capture_output=True,
                        text=True
                    )

                    # Check if VPinballX.ini was created
                    vpx_ini_path = Path.home() / ".vpinball" / "VPinballX.ini"
                    if vpx_ini_path.exists():
                        self.download_log.append(f"✓ VPinballX.ini created at: {vpx_ini_path}")
                    else:
                        self.download_log.append("⚠ VPinballX.ini not found - you may need to run VPinball manually once")

                except subprocess.TimeoutExpired:
                    # This is expected - VPinball might open a window that needs to be closed
                    self.download_log.append("VPinball launched (you may need to close it)")
                    vpx_ini_path = Path.home() / ".vpinball" / "VPinballX.ini"
                    if vpx_ini_path.exists():
                        self.download_log.append(f"✓ VPinballX.ini created at: {vpx_ini_path}")
                except Exception as e:
                    self.download_log.append(f"Note: Could not auto-launch VPinball: {e}")
                    self.download_log.append("Please run VPinball once manually to create VPinballX.ini")

            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)

    def save_config(self):
        """Save VPX configuration"""
        table_dir = self.table_dir.text()
        media_dir = self.media_dir.text()

        # Guard: a Table/Media directory set inside the ROMs folder mixes
        # downloaded media in with the .zip ROMs and later breaks the database's
        # stored media paths. Warn and require confirmation before saving.
        offenders = []
        if path_inside_roms(table_dir):
            offenders.append(f"  • Table Directory → {table_dir}")
        if path_inside_roms(media_dir):
            offenders.append(f"  • Media Directory → {media_dir}")
        if offenders:
            reply = QMessageBox.warning(
                self,
                "Directory inside ROMs folder",
                "These setting(s) point inside your ROMs folder:\n\n"
                + "\n".join(offenders)
                + "\n\nMedia downloaded by the Table Manager would be written "
                "here and mixed in with your .zip ROM files. This is almost "
                "certainly a mistake.\n\nSave anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return  # abort save; let the user correct the path

        self.config.vpx.executable_path = self.exe_path.text()
        self.config.vpx.table_directory = table_dir
        self.config.vpx.media_directory = media_dir

        # Save BGSet value to VPinballX.ini
        bgset = self.mode_combo.currentData()
        self.vpx_manager.write_bgset(bgset)


class KeyboardConfigTab(QWidget):
    """Tab for keyboard configuration"""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        form = QFormLayout()

        # Create key capture buttons
        self.key_buttons = {}

        key_actions = [
            ('exit_key', 'Exit Application'),
            ('select_key', 'Select/Launch Table'),
            ('left_key', 'Navigate Left'),
            ('right_key', 'Navigate Right'),
        ]

        for key_attr, label in key_actions:
            current_key = getattr(self.config.input, key_attr, "")
            button = KeyCaptureButton(current_key)
            self.key_buttons[key_attr] = button
            form.addRow(f"{label}:", button)

        layout.addLayout(form)
        layout.addStretch()
        self.setLayout(layout)

    def save_config(self):
        """Save keyboard configuration"""
        for key_attr, button in self.key_buttons.items():
            setattr(self.config.input, key_attr, button.current_key)


class JoystickConfigTab(QWidget):
    """Tab for joystick configuration"""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.vpx_manager = VPXIniManager()
        self.gc_manager = GameControllerManager()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Joystick info
        info_label = QLabel()
        try:
            if not pygame.get_init():
                pygame.init()
            pygame.joystick.init()

            if pygame.joystick.get_count() > 0:
                joy = pygame.joystick.Joystick(0)
                joy.init()
                info_label.setText(f"Joystick detected: {joy.get_name()}\nButtons: {joy.get_numbuttons()}")
            else:
                info_label.setText("No joystick detected")
        except:
            info_label.setText("Error initializing joystick")

        layout.addWidget(info_label)

        # Enable checkbox
        self.enabled = QCheckBox("Enable Joystick Input")
        self.enabled.setChecked(self.config.input.joystick_enabled)
        layout.addWidget(self.enabled)

        # Read button mappings from VPinballX.ini first, fall back to PinballUX config
        vpx_buttons = self.vpx_manager.read_joystick_config()

        # Button mappings
        form = QFormLayout()

        self.button_widgets = {}

        button_actions = [
            ('WHEEL_LEFT', 'Navigate Left'),
            ('WHEEL_RIGHT', 'Navigate Right'),
            ('SELECT', 'Select/Launch Table'),
            ('LEFT_FLIPPER', 'Left Flipper'),
            ('RIGHT_FLIPPER', 'Right Flipper'),
            ('PLUNGER', 'Plunger'),
            ('START', 'Start Game'),
            ('MENU', 'Menu/Add Credit'),
            ('LEFT_MAGNASAVE', 'Left MagnaSave'),
            ('RIGHT_MAGNASAVE', 'Right MagnaSave'),
            ('EXIT_TABLE', 'Exit Table'),
        ]

        for action, label in button_actions:
            # Use VPX config if available, otherwise fall back to PinballUX config
            if action in vpx_buttons:
                current_button = vpx_buttons[action]
            else:
                current_button = self.config.input.joystick_buttons.get(action, -1)

            button = JoystickButton(action, current_button)
            self.button_widgets[action] = button
            form.addRow(f"{label}:", button)

        layout.addLayout(form)
        layout.addStretch()
        self.setLayout(layout)

    def save_config(self):
        """Save joystick configuration"""
        self.config.input.joystick_enabled = self.enabled.isChecked()

        for action, button in self.button_widgets.items():
            btn_num = button.get_button()
            if btn_num >= 0:
                self.config.input.joystick_buttons[action] = btn_num

        # Save to VPinballX.ini
        self._save_to_vpx_ini()

        # Save to gamecontroller database for SDL/VPinball
        self._save_to_gamecontroller_db()

    def _save_to_vpx_ini(self):
        """Save joystick button mappings to VPinballX.ini"""
        vpx_path = Path.home() / ".vpinball" / "VPinballX.ini"

        if not vpx_path.exists():
            return  # VPX config doesn't exist yet

        # Map PinballUX actions to VPX ini keys
        vpx_mappings = {}

        if 'LEFT_FLIPPER' in self.config.input.joystick_buttons:
            vpx_mappings['JoyLFlipKey'] = self.config.input.joystick_buttons['LEFT_FLIPPER']
        if 'RIGHT_FLIPPER' in self.config.input.joystick_buttons:
            vpx_mappings['JoyRFlipKey'] = self.config.input.joystick_buttons['RIGHT_FLIPPER']
        if 'PLUNGER' in self.config.input.joystick_buttons:
            vpx_mappings['JoyPlungerKey'] = self.config.input.joystick_buttons['PLUNGER']
        if 'START' in self.config.input.joystick_buttons:
            vpx_mappings['JoyStartGameKey'] = self.config.input.joystick_buttons['START']
        if 'MENU' in self.config.input.joystick_buttons:
            vpx_mappings['JoyAddCreditKey'] = self.config.input.joystick_buttons['MENU']
        if 'LEFT_MAGNASAVE' in self.config.input.joystick_buttons:
            vpx_mappings['JoyLMagnaSave'] = self.config.input.joystick_buttons['LEFT_MAGNASAVE']
        if 'RIGHT_MAGNASAVE' in self.config.input.joystick_buttons:
            vpx_mappings['JoyRMagnaSave'] = self.config.input.joystick_buttons['RIGHT_MAGNASAVE']
        if 'EXIT_TABLE' in self.config.input.joystick_buttons:
            vpx_mappings['JoyExitGameKey'] = self.config.input.joystick_buttons['EXIT_TABLE']

        if not vpx_mappings:
            return  # Nothing to save

        try:
            # Create backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = vpx_path.parent / f"VPinballX.ini.backup_{timestamp}"
            shutil.copy2(vpx_path, backup_path)

            # Read the file
            with open(vpx_path, 'r') as f:
                lines = f.readlines()

            # Track which keys we've updated
            updated_keys = set()

            # Update existing joystick button lines
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                for key, value in vpx_mappings.items():
                    key_lower = key.lower()
                    if line_lower.startswith(f"{key_lower} =") or line_lower.startswith(f"{key_lower}="):
                        original_key = line.split('=')[0].strip()
                        lines[i] = f"{original_key} = {value}\n"
                        updated_keys.add(key.lower())
                        break

            # Add any missing keys at the end of [Player] section
            missing_keys = set(k.lower() for k in vpx_mappings.keys()) - updated_keys
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
                    for key, value in vpx_mappings.items():
                        if key.lower() in missing_keys:
                            lines.insert(insert_idx, f"{key} = {value}\n")

            # Write back
            with open(vpx_path, 'w') as f:
                f.writelines(lines)

        except Exception as e:
            # Silently fail - VPX config is optional
            pass

    def _save_to_gamecontroller_db(self):
        """Save joystick mappings to SDL gamecontroller database"""
        try:
            # Generate mapping from actual button configuration
            success = self.gc_manager.update_from_button_mappings(self.config.input.joystick_buttons)

            if success:
                print(f"✓ VPinball-compatible gamecontroller mapping saved")
                return True
            else:
                print("⚠ Could not save gamecontroller mapping (no joystick detected?)")
                return False

        except Exception as e:
            # Don't fail the entire save if this doesn't work
            print(f"Warning: Could not update gamecontroller database: {e}")
            import traceback
            traceback.print_exc()
            return False


class AudioConfigTab(QWidget):
    """Tab for audio configuration"""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.table_audio = QCheckBox("Play table audio when navigating")
        self.table_audio.setChecked(self.config.audio.table_audio)
        layout.addWidget(self.table_audio)

        layout.addStretch()
        self.setLayout(layout)

    def save_config(self):
        """Save audio configuration"""
        self.config.audio.table_audio = self.table_audio.isChecked()


class SetupWindow(QMainWindow):
    """Main setup window"""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("PinballUX Setup")
        self.setMinimumSize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Tab widget
        tabs = QTabWidget()

        # Create tabs
        self.display_tab = DisplayConfigTab(self.config)
        self.vpx_tab = VPXConfigTab(self.config)
        self.keyboard_tab = KeyboardConfigTab(self.config)
        self.joystick_tab = JoystickConfigTab(self.config)
        self.audio_tab = AudioConfigTab(self.config)

        tabs.addTab(self.vpx_tab, "Visual Pinball")
        tabs.addTab(self.display_tab, "Displays")
        tabs.addTab(self.keyboard_tab, "Keyboard")
        tabs.addTab(self.joystick_tab, "Joystick")
        tabs.addTab(self.audio_tab, "Audio")

        layout.addWidget(tabs)

        # Buttons
        button_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset All to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        reset_btn.setStyleSheet("color: #ff6666; font-size: 13px; padding: 8px;")
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        save_btn.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def reset_to_defaults(self):
        """Delete all config and credentials, reload with defaults."""
        reply = QMessageBox.warning(
            self,
            "Reset All Configuration",
            "This will delete all saved configuration and FTP credentials and reset everything to defaults.\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        config_dir = Path.home() / ".config" / "pinballux"
        for filename in ("config.json", "ftp_credentials.json"):
            path = config_dir / filename
            if path.exists():
                path.unlink()

        # Reload with fresh defaults
        self.config = Config()
        self.display_tab.config = self.config
        self.vpx_tab.config = self.config
        self.keyboard_tab.config = self.config
        self.joystick_tab.config = self.config
        self.audio_tab.config = self.config

        self.display_tab.init_ui()
        self.vpx_tab.init_ui()
        self.keyboard_tab.init_ui()
        self.joystick_tab.init_ui()
        self.audio_tab.init_ui()

        QMessageBox.information(self, "Reset Complete", "Configuration reset to defaults.\nFTP credentials have also been cleared.")

    def save_config(self):
        """Save all configuration"""
        try:
            # Save VPX tab first so table/media directories are updated
            # before other tabs that depend on them (like display tab)
            self.vpx_tab.save_config()
            self.display_tab.save_config()
            self.keyboard_tab.save_config()
            self.joystick_tab.save_config()
            self.audio_tab.save_config()

            # Write to file
            self.config.save()

            # Check if VPX config exists
            vpx_path = Path.home() / ".vpinball" / "VPinballX.ini"
            vpx_msg = ""
            if vpx_path.exists():
                vpx_msg = f"\n\nVPinballX.ini updated:\n{vpx_path}\n(Display positions, joystick mappings)"

            # Check if ScreenRes.txt was updated
            screenres_path = Path.home() / ".vpinball" / "data" / "tables" / "ScreenRes.txt"
            screenres_msg = ""
            if screenres_path.exists():
                screenres_msg = f"\n\nScreenRes.txt updated:\n{screenres_path}\n(B2S Server display configuration)"

            # Check if gamecontroller db was updated
            gc_path = Path.home() / ".vpinball" / "gamecontrollerdb.txt"
            gc_msg = ""
            if gc_path.exists():
                gc_msg = f"\n\ngamecontrollerdb.txt updated:\n{gc_path}\n(Joystick GUID and SDL mappings)"

            QMessageBox.information(
                self,
                "Success",
                f"Configuration saved successfully!\n\nPinballUX config:\n{self.config.config_file}{vpx_msg}{screenres_msg}{gc_msg}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error saving configuration:\n{e}"
            )


def main():
    # Ensure the VPinMAME roms symlink is in place before launching the UI
    setup_vpinmame_roms_symlink()

    app = QApplication(sys.argv)
    window = SetupWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
