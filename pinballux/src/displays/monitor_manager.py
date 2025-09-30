"""
Monitor and display management for multi-monitor setups
"""

from typing import Dict, Optional, List
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QScreen

from ..core.config import Config, MonitorConfig
from ..core.logger import get_logger
from .base_display import BaseDisplay
from .backglass_display import BackglassDisplay
from .dmd_display import DMDDisplay
from .topper_display import TopperDisplay


class MonitorManager(QObject):
    """Manages multiple monitors and their associated displays"""

    # Signals
    display_created = pyqtSignal(str, QWidget)  # display_type, widget
    display_closed = pyqtSignal(str)  # display_type

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.logger = get_logger(__name__)

        # Active display windows
        self.displays: Dict[str, BaseDisplay] = {}

        # Available screens
        self.screens: Dict[str, QScreen] = {}

        self._detect_screens()

    def _detect_screens(self):
        """Detect available screens/monitors"""
        app = QApplication.instance()
        if app:
            screens = app.screens()
            self.logger.info(f"Detected {len(screens)} screen(s)")

            for i, screen in enumerate(screens):
                screen_name = screen.name() or f"Screen_{i}"
                self.screens[screen_name] = screen
                geometry = screen.geometry()
                self.logger.info(
                    f"Screen '{screen_name}': {geometry.width()}x{geometry.height()} "
                    f"at ({geometry.x()}, {geometry.y()})"
                )

    def get_screen_by_position(self, x: int, y: int) -> Optional[QScreen]:
        """Find screen that contains the given position"""
        for screen in self.screens.values():
            if screen.geometry().contains(x, y):
                return screen
        return None

    def create_display(self, display_type: str, monitor_config: MonitorConfig) -> Optional[BaseDisplay]:
        """Create a display window for the specified monitor"""
        try:
            # Create the appropriate display type
            display = None

            if display_type == "backglass":
                display = BackglassDisplay(monitor_config)
            elif display_type in ["dmd", "fulldmd"]:
                display = DMDDisplay(monitor_config, is_full_dmd=(display_type == "fulldmd"))
            elif display_type == "topper":
                display = TopperDisplay(monitor_config)
            else:
                self.logger.warning(f"Unknown display type: {display_type}")
                return None

            # Position the display
            display.setGeometry(
                monitor_config.x,
                monitor_config.y,
                monitor_config.width,
                monitor_config.height
            )

            # Store the display
            self.displays[display_type] = display

            self.logger.info(f"Created {display_type} display at ({monitor_config.x}, {monitor_config.y})")
            self.display_created.emit(display_type, display)

            return display

        except Exception as e:
            self.logger.error(f"Failed to create {display_type} display: {e}")
            return None

    def show_displays(self):
        """Show all configured display windows"""
        # Create and show backglass display
        if self.config.displays.backglass and self.config.displays.backglass.enabled:
            if "backglass" not in self.displays:
                self.create_display("backglass", self.config.displays.backglass)
            if "backglass" in self.displays:
                self.displays["backglass"].show()

        # Create and show DMD display
        if self.config.displays.dmd and self.config.displays.dmd.enabled:
            if "dmd" not in self.displays:
                self.create_display("dmd", self.config.displays.dmd)
            if "dmd" in self.displays:
                self.displays["dmd"].show()

        # Create and show FullDMD display
        if self.config.displays.fulldmd and self.config.displays.fulldmd.enabled:
            if "fulldmd" not in self.displays:
                self.create_display("fulldmd", self.config.displays.fulldmd)
            if "fulldmd" in self.displays:
                self.displays["fulldmd"].show()

        # Create and show topper display
        if self.config.displays.topper and self.config.displays.topper.enabled:
            if "topper" not in self.displays:
                self.create_display("topper", self.config.displays.topper)
            if "topper" in self.displays:
                self.displays["topper"].show()

    def close_displays(self):
        """Close all display windows"""
        for display_type, display in self.displays.items():
            try:
                display.close()
                self.display_closed.emit(display_type)
            except Exception as e:
                self.logger.error(f"Error closing {display_type} display: {e}")

        self.displays.clear()

    def get_display(self, display_type: str) -> Optional[BaseDisplay]:
        """Get a specific display window"""
        return self.displays.get(display_type)

    def update_display_content(self, display_type: str, content_data: dict):
        """Update content for a specific display"""
        display = self.displays.get(display_type)
        if display:
            display.update_content(content_data)

    def list_screens(self) -> List[Dict[str, any]]:
        """Get list of available screens with their properties"""
        screen_list = []
        for name, screen in self.screens.items():
            geometry = screen.geometry()
            screen_list.append({
                'name': name,
                'x': geometry.x(),
                'y': geometry.y(),
                'width': geometry.width(),
                'height': geometry.height(),
                'dpi': screen.logicalDotsPerInch()
            })
        return screen_list