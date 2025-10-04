#!/usr/bin/env python3
"""
PinballUX Setup GUI
Configuration tool for PinballUX with display, input, and VPX settings
"""

import sys
import os
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QFormLayout,
    QSpinBox, QCheckBox, QGroupBox, QFileDialog, QMessageBox,
    QComboBox, QListWidget, QListWidgetItem, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pinballux.src.core.config import Config, MonitorConfig
import pygame


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
        self.init_ui()

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
        group = QGroupBox(label)
        layout = QFormLayout()

        # Get current config
        current = getattr(self.config.displays, display_type)

        # Enabled checkbox
        enabled = QCheckBox()
        enabled.setChecked(current.enabled if current else False)
        layout.addRow("Enabled:", enabled)

        # Screen number
        screen_num = QSpinBox()
        screen_num.setRange(0, 10)
        screen_num.setValue(current.screen_number if current else 0)
        layout.addRow("Screen Number:", screen_num)

        # Rotation
        rotation = QComboBox()
        rotation.addItems(["0°", "90°", "180°", "270°"])
        if current:
            rotation.setCurrentIndex([0, 90, 180, 270].index(current.rotation) if current.rotation in [0, 90, 180, 270] else 0)
        layout.addRow("Rotation:", rotation)

        # DMD mode (only for DMD displays)
        dmd_mode = None
        if 'dmd' in display_type:
            dmd_mode = QComboBox()
            dmd_mode.addItems(["Full Screen", "Native Size"])
            if current:
                dmd_mode.setCurrentIndex(0 if current.dmd_mode == "full" else 1)
            layout.addRow("DMD Mode:", dmd_mode)

        group.setLayout(layout)

        # Store widgets for later retrieval
        self.display_widgets[display_type] = {
            'enabled': enabled,
            'screen_number': screen_num,
            'rotation': rotation,
            'dmd_mode': dmd_mode
        }

        return group

    def save_config(self):
        """Save display configuration"""
        for display_type, widgets in self.display_widgets.items():
            enabled = widgets['enabled'].isChecked()
            screen_number = widgets['screen_number'].value()
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


class VPXConfigTab(QWidget):
    """Tab for VPX configuration"""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
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
            ('up_key', 'Navigate Up'),
            ('down_key', 'Navigate Down'),
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

            QMessageBox.information(
                self,
                "Success",
                f"Configuration saved successfully!\n\nConfig file: {self.config.config_file}"
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
