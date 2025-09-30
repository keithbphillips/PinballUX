"""
Topper display component for pinball cabinet topper monitor
"""

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QFont, QColor, QPalette, QLinearGradient

from ..core.config import MonitorConfig
from .base_display import BaseDisplay


class TopperDisplay(BaseDisplay):
    """Display window for topper effects and lighting"""

    # Signals
    topper_effect_changed = pyqtSignal(str)  # effect name

    def __init__(self, monitor_config: MonitorConfig):
        super().__init__(monitor_config)

        # Current state
        self.current_effect = "idle"
        self.current_table = None
        self.effect_intensity = 0.5

        # Animation timers
        self.effect_timer = QTimer()
        self.effect_timer.timeout.connect(self._update_effect)

        # Color cycling for attract mode
        self.color_cycle_timer = QTimer()
        self.color_cycle_timer.timeout.connect(self._cycle_colors)
        self.current_color_index = 0
        self.attract_colors = [
            "#ff0000", "#ff8800", "#ffff00", "#00ff00",
            "#0088ff", "#0000ff", "#8800ff", "#ff0088"
        ]

    def _setup_layout(self):
        """Set up the topper display layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main effect area
        self.effect_label = QLabel()
        self.effect_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.effect_label.setStyleSheet("background-color: black; color: white;")
        layout.addWidget(self.effect_label, 1)

        # Optional status bar
        self.status_layout = QHBoxLayout()
        self.status_layout.setContentsMargins(10, 5, 10, 5)

        # Table name (smaller font for topper)
        self.table_name_label = QLabel("PinballUX")
        self.table_name_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        self.table_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Effect status
        self.effect_status_label = QLabel("Ready")
        self.effect_status_label.setStyleSheet("color: #00ff00; font-size: 14px;")
        self.effect_status_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.status_layout.addWidget(self.table_name_label)
        self.status_layout.addStretch()
        self.status_layout.addWidget(self.effect_status_label)

        layout.addLayout(self.status_layout)

        # Set initial state
        self._show_idle_effect()

    def update_content(self, content_data: dict):
        """Update topper content"""
        table_name = content_data.get('table_name', 'Unknown Table')
        effect = content_data.get('effect', 'idle')
        intensity = content_data.get('intensity', 0.5)
        topper_image = content_data.get('topper_image', '')

        # Update table info
        self.table_name_label.setText(table_name)
        self.current_table = content_data

        # Update effect
        self.set_effect(effect, intensity)

        # Update topper image if provided
        if topper_image:
            self.show_image(topper_image, self.effect_label)

    def set_effect(self, effect_name: str, intensity: float = 0.5):
        """Set the current topper effect"""
        self.current_effect = effect_name
        self.effect_intensity = max(0.0, min(1.0, intensity))

        # Stop any current effects
        self.effect_timer.stop()
        self.color_cycle_timer.stop()

        # Start the requested effect
        if effect_name == "idle":
            self._show_idle_effect()
        elif effect_name == "attract":
            self._show_attract_effect()
        elif effect_name == "table_selected":
            self._show_table_selected_effect()
        elif effect_name == "launching":
            self._show_launching_effect()
        elif effect_name == "playing":
            self._show_playing_effect()
        elif effect_name == "high_score":
            self._show_high_score_effect()
        else:
            self._show_custom_effect(effect_name)

        self.effect_status_label.setText(effect_name.replace("_", " ").title())
        self.topper_effect_changed.emit(effect_name)

    def _show_idle_effect(self):
        """Show idle/standby effect"""
        self.effect_label.clear()
        self.effect_label.setText("PinballUX\nReady")
        self.effect_label.setStyleSheet(
            "background-color: #001122; color: #4488cc; "
            "font-size: 24px; font-weight: bold; "
            "border: 1px solid #2244aa;"
        )

    def _show_attract_effect(self):
        """Show attract mode effect with color cycling"""
        self.effect_label.setText("Select a Table")
        self.effect_label.setStyleSheet(
            f"background-color: black; color: {self.attract_colors[0]}; "
            "font-size: 28px; font-weight: bold; "
            "border: 2px solid #333333;"
        )

        # Start color cycling
        self.color_cycle_timer.start(500)  # Change color every 500ms

    def _show_table_selected_effect(self):
        """Show table selection confirmation effect"""
        self.effect_label.setText("Loading Table...")
        self.effect_label.setStyleSheet(
            "background-color: #002200; color: #00ff00; "
            "font-size: 24px; font-weight: bold; "
            "border: 2px solid #00aa00;"
        )

        # Brief flash effect
        self.effect_timer.start(200)

    def _show_launching_effect(self):
        """Show game launching effect"""
        self.effect_label.setText("Starting Game...")
        self.effect_label.setStyleSheet(
            "background-color: #220000; color: #ff4444; "
            "font-size: 24px; font-weight: bold; "
            "border: 2px solid #aa0000;"
        )

    def _show_playing_effect(self):
        """Show effect while game is running"""
        if self.current_table:
            table_name = self.current_table.get('table_name', 'Playing')
            self.effect_label.setText(f"Playing:\n{table_name}")
        else:
            self.effect_label.setText("Game Active")

        self.effect_label.setStyleSheet(
            "background-color: #001100; color: #44ff44; "
            "font-size: 20px; font-weight: bold; "
            "border: 2px solid #00aa00;"
        )

    def _show_high_score_effect(self):
        """Show high score celebration effect"""
        self.effect_label.setText("HIGH SCORE!\nCongratulations!")
        self.effect_label.setStyleSheet(
            "background-color: #ffaa00; color: #ffffff; "
            "font-size: 24px; font-weight: bold; "
            "border: 3px solid #ff8800;"
        )

        # Flash effect for celebration
        self.effect_timer.start(100)

    def _show_custom_effect(self, effect_name: str):
        """Show a custom effect"""
        self.effect_label.setText(effect_name.replace("_", " ").title())
        self.effect_label.setStyleSheet(
            "background-color: #333333; color: #ffffff; "
            "font-size: 22px; font-weight: bold; "
            "border: 2px solid #666666;"
        )

    def _cycle_colors(self):
        """Cycle through attract mode colors"""
        self.current_color_index = (self.current_color_index + 1) % len(self.attract_colors)
        current_color = self.attract_colors[self.current_color_index]

        self.effect_label.setStyleSheet(
            f"background-color: black; color: {current_color}; "
            "font-size: 28px; font-weight: bold; "
            f"border: 2px solid {current_color};"
        )

    def _update_effect(self):
        """Update dynamic effects"""
        if self.current_effect == "table_selected":
            # Stop flashing after a few cycles
            self.effect_timer.stop()
        elif self.current_effect == "high_score":
            # Continue flashing for high score
            current_style = self.effect_label.styleSheet()
            if "background-color: #ffaa00" in current_style:
                self.effect_label.setStyleSheet(
                    "background-color: #ff0000; color: #ffffff; "
                    "font-size: 24px; font-weight: bold; "
                    "border: 3px solid #ffff00;"
                )
            else:
                self.effect_label.setStyleSheet(
                    "background-color: #ffaa00; color: #ffffff; "
                    "font-size: 24px; font-weight: bold; "
                    "border: 3px solid #ff8800;"
                )

    def flash_message(self, message: str, duration: int = 3000, color: str = "#ff8800"):
        """Flash a temporary message"""
        original_effect = self.current_effect

        # Show flash message
        self.effect_label.setText(message)
        self.effect_label.setStyleSheet(
            f"background-color: black; color: {color}; "
            "font-size: 26px; font-weight: bold; "
            f"border: 2px solid {color};"
        )

        # Restore original effect after duration
        QTimer.singleShot(duration, lambda: self.set_effect(original_effect))

    def clear_content(self):
        """Clear topper content"""
        super().clear_content()
        self.effect_timer.stop()
        self.color_cycle_timer.stop()
        self._show_idle_effect()
        self.current_table = None