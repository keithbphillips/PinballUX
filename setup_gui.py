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
    QSpinBox, QCheckBox, QGroupBox, QFileDialog, QMessageBox,
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
            key = QKeySequence(event.key()).toString()
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
    """Tab for display configuration"""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.vpx_manager = VPXIniManager()
        self.screens = self._detect_screens()
        self.init_ui()

    def _detect_screens(self):
        """Detect available screens and their properties"""
        app = QApplication.instance()
        screens = []
        for i, screen in enumerate(app.screens()):
            geometry = screen.geometry()
            screens.append({
                'index': i,
                'name': screen.name(),
                'width': geometry.width(),
                'height': geometry.height(),
                'x': geometry.x(),
                'y': geometry.y()
            })
        return screens

    def init_ui(self):
        layout = QVBoxLayout()

        # Scroll area for display configs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        # Create config groups for each display type
        self.display_widgets = {}

        display_types = [
            ('playfield', 'Playfield Display'),
            ('backglass', 'Backglass Display'),
            ('dmd', 'DMD Display'),
            ('fulldmd', 'Full DMD Display'),
            ('topper', 'Topper Display')
        ]

        for display_type, display_label in display_types:
            group = self.create_display_group(display_type, display_label)
            scroll_layout.addWidget(group)

        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        self.setLayout(layout)

    def create_display_group(self, display_type: str, label: str) -> QGroupBox:
        """Create a configuration group for a display"""
        main_group = QGroupBox(label)
        main_layout = QVBoxLayout()

        # PinballUX Configuration
        ux_group = QGroupBox("PinballUX Settings")
        ux_layout = QFormLayout()

        # Get current config
        current = getattr(self.config.displays, display_type)

        # Enabled checkbox
        enabled = QCheckBox()
        enabled.setChecked(current.enabled if current else False)
        ux_layout.addRow("Enabled:", enabled)

        # Screen selection dropdown
        screen_combo = QComboBox()
        for screen in self.screens:
            screen_combo.addItem(
                f"Screen {screen['index']}: {screen['name']} ({screen['width']}x{screen['height']})",
                screen['index']
            )

        # Set current screen
        if current and current.screen_number < len(self.screens):
            screen_combo.setCurrentIndex(current.screen_number)
        ux_layout.addRow("Screen:", screen_combo)

        # Rotation
        rotation = QComboBox()
        rotation.addItems(["0°", "90°", "180°", "270°"])
        if current:
            rotation.setCurrentIndex([0, 90, 180, 270].index(current.rotation) if current.rotation in [0, 90, 180, 270] else 0)
        ux_layout.addRow("Rotation:", rotation)

        # DMD mode (only for DMD displays)
        dmd_mode = None
        if 'dmd' in display_type:
            dmd_mode = QComboBox()
            dmd_mode.addItems(["Full Screen", "Native Size"])
            if current:
                dmd_mode.setCurrentIndex(0 if current.dmd_mode == "full" else 1)
            ux_layout.addRow("DMD Mode:", dmd_mode)

        ux_group.setLayout(ux_layout)
        main_layout.addWidget(ux_group)

        # VPinballX Configuration
        vpx_group = QGroupBox("VPinballX.ini Settings (Auto-populated from Screen)")
        vpx_layout = QFormLayout()

        # Load VPX config
        vpx_config = self.vpx_manager.read_display_config(display_type)

        # Position X (auto-populated from screen, but adjustable)
        vpx_x = QSpinBox()
        vpx_x.setRange(-10000, 10000)
        vpx_x.setValue(vpx_config.get('x', 0))
        vpx_layout.addRow("X Position:", vpx_x)

        # Position Y (auto-populated from screen, but adjustable)
        vpx_y = QSpinBox()
        vpx_y.setRange(-10000, 10000)
        vpx_y.setValue(vpx_config.get('y', 0))
        vpx_layout.addRow("Y Position:", vpx_y)

        # Width (editable only for dmd and b2sdmd)
        vpx_width = QSpinBox()
        vpx_width.setRange(0, 10000)
        vpx_width.setValue(vpx_config.get('width', 1920))
        # Only allow adjustment for regular DMD and B2SDMD
        if display_type not in ['dmd', 'b2sdmd']:
            vpx_width.setEnabled(False)
        vpx_layout.addRow("Width:", vpx_width)

        # Height (editable only for dmd and b2sdmd)
        vpx_height = QSpinBox()
        vpx_height.setRange(0, 10000)
        vpx_height.setValue(vpx_config.get('height', 1080))
        # Only allow adjustment for regular DMD and B2SDMD
        if display_type not in ['dmd', 'b2sdmd']:
            vpx_height.setEnabled(False)
        vpx_layout.addRow("Height:", vpx_height)

        # VPX Rotation (for displays that support it)
        vpx_rotation = None
        if display_type in ['backglass', 'dmd', 'fulldmd', 'b2sdmd']:
            vpx_rotation = QComboBox()
            vpx_rotation.addItems(["0°", "90°", "180°", "270°"])
            vpx_rot_value = vpx_config.get('rotation', 0)
            if isinstance(vpx_rot_value, int) and vpx_rot_value in [0, 90, 180, 270]:
                vpx_rotation.setCurrentIndex([0, 90, 180, 270].index(vpx_rot_value))
            vpx_layout.addRow("VPX Rotation:", vpx_rotation)

        vpx_group.setLayout(vpx_layout)
        main_layout.addWidget(vpx_group)

        main_group.setLayout(main_layout)

        # Store widgets for later retrieval
        self.display_widgets[display_type] = {
            'enabled': enabled,
            'screen_combo': screen_combo,
            'rotation': rotation,
            'dmd_mode': dmd_mode,
            'vpx_x': vpx_x,
            'vpx_y': vpx_y,
            'vpx_width': vpx_width,
            'vpx_height': vpx_height,
            'vpx_rotation': vpx_rotation
        }

        # Connect screen selection to auto-populate VPX fields
        screen_combo.currentIndexChanged.connect(
            lambda: self._update_vpx_fields(display_type)
        )

        # Always populate width/height from selected screen (they're read-only)
        self._update_vpx_fields(display_type)

        return main_group

    def _update_vpx_fields(self, display_type: str):
        """Auto-populate VPX position/size fields based on selected screen"""
        widgets = self.display_widgets.get(display_type)
        if not widgets:
            return

        screen_idx = widgets['screen_combo'].currentData()
        if screen_idx is None or screen_idx >= len(self.screens):
            return

        screen = self.screens[screen_idx]

        # For regular DMD and B2SDMD, don't auto-populate width/height - keep existing VPX.ini values
        # But still update X/Y position
        if display_type in ['dmd', 'b2sdmd']:
            widgets['vpx_x'].setValue(screen['x'])
            widgets['vpx_y'].setValue(screen['y'])
            return

        # Update all VPX position and size fields for other displays
        widgets['vpx_x'].setValue(screen['x'])
        widgets['vpx_y'].setValue(screen['y'])
        widgets['vpx_width'].setValue(screen['width'])
        widgets['vpx_height'].setValue(screen['height'])

    def save_config(self):
        """Save display configuration to both PinballUX and VPinballX.ini"""
        for display_type, widgets in self.display_widgets.items():
            # Save PinballUX configuration
            enabled = widgets['enabled'].isChecked()
            screen_number = widgets['screen_combo'].currentData()
            rotation_idx = widgets['rotation'].currentIndex()
            rotation = [0, 90, 180, 270][rotation_idx]

            dmd_mode = "full"
            if widgets['dmd_mode']:
                dmd_mode = "full" if widgets['dmd_mode'].currentIndex() == 0 else "native"

            if enabled:
                monitor_config = MonitorConfig(
                    name=display_type.capitalize(),
                    screen_number=screen_number,
                    rotation=rotation,
                    enabled=enabled,
                    dmd_mode=dmd_mode
                )
                setattr(self.config.displays, display_type, monitor_config)
            else:
                setattr(self.config.displays, display_type, None)

            # Save VPinballX.ini configuration
            vpx_config = {
                'x': widgets['vpx_x'].value(),
                'y': widgets['vpx_y'].value(),
                'width': widgets['vpx_width'].value(),
                'height': widgets['vpx_height'].value()
            }

            # Add rotation if supported
            if widgets['vpx_rotation']:
                vpx_rot_idx = widgets['vpx_rotation'].currentIndex()
                vpx_config['rotation'] = [0, 90, 180, 270][vpx_rot_idx]

            # Write to VPinballX.ini
            self.vpx_manager.write_display_config(display_type, vpx_config)


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
        self.download_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

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
            "https://github.com/vpinball/vpinball/releases/download/v10.8.0-2051-28dd6c3/VPinballX_GL-10.8.0-2052-5a81d4e-Release-linux-x64.zip"
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
        dest_dir = Path(project_root) / "vpinball"

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
            dest_dir = Path(project_root) / "vpinball"
            exe_path = dest_dir / "VPinballX_GL"
            if exe_path.exists():
                self.exe_path.setText(str(exe_path))
                self.download_log.append(f"Executable path updated to: {exe_path}")

            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)

    def save_config(self):
        """Save VPX configuration"""
        self.config.vpx.executable_path = self.exe_path.text()
        self.config.vpx.table_directory = self.table_dir.text()
        self.config.vpx.media_directory = self.media_dir.text()


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

        # Also save to VPinballX.ini
        self._save_to_vpx_ini()

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

        tabs.addTab(self.display_tab, "Displays")
        tabs.addTab(self.vpx_tab, "Visual Pinball")
        tabs.addTab(self.keyboard_tab, "Keyboard")
        tabs.addTab(self.joystick_tab, "Joystick")
        tabs.addTab(self.audio_tab, "Audio")

        layout.addWidget(tabs)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        save_btn.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def save_config(self):
        """Save all configuration"""
        try:
            # Save from each tab
            self.display_tab.save_config()
            self.vpx_tab.save_config()
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

            QMessageBox.information(
                self,
                "Success",
                f"Configuration saved successfully!\n\nPinballUX config:\n{self.config.config_file}{vpx_msg}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error saving configuration:\n{e}"
            )


def main():
    app = QApplication(sys.argv)
    window = SetupWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
