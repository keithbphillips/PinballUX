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

        # Available screens by index
        self.screens: List[QScreen] = []

        # Whether show_displays() has been called (so late-arriving screens auto-show)
        self._displays_requested = False

        self._detect_screens()

        # Connect to screen-added signal so secondary monitors that come online
        # after startup (common on Pi/labwc at boot) still get their displays.
        app = QApplication.instance()
        if app:
            app.screenAdded.connect(self._on_screen_added)

    def _on_screen_added(self, screen: QScreen):
        """Called when a new monitor becomes available after startup."""
        self.logger.info(f"Screen added: {screen.name()} — re-detecting screens")
        self._detect_screens()
        if self._displays_requested:
            self.show_displays()

    def _detect_screens(self):
        """Detect available screens/monitors"""
        app = QApplication.instance()
        if app:
            self.screens = app.screens()
            self.logger.info(f"Detected {len(self.screens)} screen(s)")

            for i, screen in enumerate(self.screens):
                screen_name = screen.name() or f"Screen_{i}"
                geometry = screen.geometry()
                self.logger.info(
                    f"Screen {i} ('{screen_name}'): {geometry.width()}x{geometry.height()} "
                    f"at ({geometry.x()}, {geometry.y()})"
                )

    def get_screen_by_number(self, screen_number: int) -> Optional[QScreen]:
        """Get screen by index number"""
        if 0 <= screen_number < len(self.screens):
            return self.screens[screen_number]
        return None

    def _find_screen_containing(self, x: int, y: int) -> Optional[QScreen]:
        """Return the QScreen whose geometry contains the given point."""
        for screen in self.screens:
            if screen.geometry().contains(x, y):
                return screen
        return None

    def _resolve_monitor_geometry(self, monitor_config: MonitorConfig) -> tuple[QScreen, int, int, int, int]:
        """Resolve final geometry for a monitor configuration

        Returns: (screen, x, y, width, height)
        Returns the target QScreen object and geometry.
        If manual overrides are set, use those. Otherwise, auto-detect from screen_number.
        """
        # When explicit coordinates are configured, find the screen that actually
        # occupies that position. Screen index ordering from the compositor is
        # non-deterministic at boot vs. an established session, so trusting
        # screen_number alone causes displays to appear on the wrong monitor.
        if all(v is not None for v in [monitor_config.x, monitor_config.y,
                                        monitor_config.width, monitor_config.height]):
            screen = self._find_screen_containing(monitor_config.x, monitor_config.y)
            if screen is None:
                self.logger.warning(
                    f"No screen found containing ({monitor_config.x}, {monitor_config.y}); "
                    f"falling back to screen_number {monitor_config.screen_number}"
                )
                screen = self.get_screen_by_number(monitor_config.screen_number)
            if screen is None:
                screen = QApplication.instance().primaryScreen()
            return (screen, monitor_config.x, monitor_config.y,
                    monitor_config.width, monitor_config.height)

        screen = self.get_screen_by_number(monitor_config.screen_number)
        if not screen:
            self.logger.error(
                f"Screen {monitor_config.screen_number} not found. "
                f"Available screens: 0-{len(self.screens)-1}"
            )
            screen = QApplication.instance().primaryScreen()
            return (screen, 0, 0, 1920, 1080)

        geometry = screen.geometry()
        return (screen, geometry.x(), geometry.y(), geometry.width(), geometry.height())

    def create_display(self, display_type: str, monitor_config: MonitorConfig) -> Optional[BaseDisplay]:
        """Create a display window for the specified monitor"""
        try:
            # Resolve geometry and target screen (auto-detect or use manual overrides)
            target_screen, x, y, width, height = self._resolve_monitor_geometry(monitor_config)

            # Create the appropriate display type, passing target screen
            display = None

            if display_type == "backglass":
                display = BackglassDisplay(monitor_config, target_screen=target_screen)
            elif display_type in ["dmd", "fulldmd"]:
                display = DMDDisplay(monitor_config, target_screen=target_screen, is_full_dmd=(display_type == "fulldmd"))
            elif display_type == "topper":
                display = TopperDisplay(monitor_config, target_screen=target_screen)
            else:
                self.logger.warning(f"Unknown display type: {display_type}")
                return None

            # Store the display
            self.displays[display_type] = display

            self.logger.info(
                f"Created {display_type} display for screen {monitor_config.screen_number} "
                f"({target_screen.name()})"
            )
            self.display_created.emit(display_type, display)

            return display

        except Exception as e:
            self.logger.error(f"Failed to create {display_type} display: {e}")
            return None

    def show_displays(self):
        """Show all configured display windows"""
        self._displays_requested = True

        for display_type, monitor_cfg in [
            ("backglass", self.config.displays.backglass),
            ("dmd", self.config.displays.dmd),
            ("fulldmd", self.config.displays.fulldmd),
            ("topper", self.config.displays.topper),
        ]:
            if not monitor_cfg or not monitor_cfg.enabled:
                continue

            # Skip if the required screen isn't available yet.
            # When explicit coordinates are configured, use the same
            # coordinate-based lookup that _resolve_monitor_geometry uses;
            # the screen_number index is unreliable after a display change.
            has_explicit_coords = all(
                v is not None for v in [monitor_cfg.x, monitor_cfg.y,
                                        monitor_cfg.width, monitor_cfg.height]
            )
            if has_explicit_coords:
                screen_available = self._find_screen_containing(
                    monitor_cfg.x, monitor_cfg.y) is not None
            else:
                screen_available = self.get_screen_by_number(
                    monitor_cfg.screen_number) is not None

            if not screen_available:
                self.logger.warning(
                    f"Screen for {display_type} not yet available "
                    f"(coords={monitor_cfg.x},{monitor_cfg.y} / "
                    f"screen_number={monitor_cfg.screen_number}) "
                    f"— will retry when screen connects"
                )
                continue

            if display_type not in self.displays:
                self.create_display(display_type, monitor_cfg)
            if display_type in self.displays:
                self.displays[display_type].show()

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

    def show_loading(self, display_type: str, table_name: str):
        """Show loading screen on a specific display"""
        display = self.displays.get(display_type)
        self.logger.debug(f"show_loading: display_type={display_type}, display={display}, has_method={hasattr(display, 'show_loading') if display else False}")
        if display and hasattr(display, 'show_loading'):
            self.logger.info(f"Calling show_loading on {display_type} display")
            display.show_loading(table_name)
        else:
            self.logger.warning(f"Cannot show loading on {display_type}: display={'found' if display else 'not found'}, has_method={hasattr(display, 'show_loading') if display else 'N/A'}")

    def hide_loading(self, display_type: str):
        """Hide loading screen on a specific display"""
        display = self.displays.get(display_type)
        if display and hasattr(display, 'hide_loading'):
            display.hide_loading()

    def list_screens(self) -> List[Dict[str, any]]:
        """Get list of available screens with their properties"""
        screen_list = []
        for i, screen in enumerate(self.screens):
            geometry = screen.geometry()
            screen_list.append({
                'number': i,
                'name': screen.name() or f"Screen_{i}",
                'x': geometry.x(),
                'y': geometry.y(),
                'width': geometry.width(),
                'height': geometry.height(),
                'dpi': screen.logicalDotsPerInch()
            })
        return screen_list