"""
Main application class for PinballUX
"""

import sys
from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QScreen

from .config import Config
from .logger import get_logger
from .vpx_launcher import LaunchManager
from ..displays.monitor_manager import MonitorManager
from ..ui.wheel_widget import WheelMainWindow
from ..database.models import DatabaseManager
from ..database.service import TableService
from ..media.manager import MediaManager


class PinballUXApp(QMainWindow):
    """Main application class"""

    # Signals
    table_selected = pyqtSignal(str)  # Table file path
    exit_requested = pyqtSignal()

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.logger = get_logger(__name__)

        # Initialize components
        self.database_manager = None
        self.table_service = None
        self.launch_manager = None
        self.monitor_manager = None
        self.main_window = None

        self._setup_application()

    def _setup_application(self):
        """Set up the main application"""
        self.logger.info("Initializing PinballUX application")

        # Initialize database
        self.database_manager = DatabaseManager()
        self.database_manager.initialize()

        # Initialize media manager
        self.media_manager = MediaManager(self.config)

        # Initialize table service with media manager
        self.table_service = TableService(self.database_manager, self.media_manager)

        # Initialize launch manager
        self.launch_manager = LaunchManager(self.config, self.table_service)

        # Initialize monitor manager
        self.monitor_manager = MonitorManager(self.config)

        # Set up the main window (wheel interface)
        self.main_window = WheelMainWindow(self.config, self.monitor_manager, self.table_service, self.launch_manager)
        self.setCentralWidget(self.main_window)

        # Connect signals
        self.main_window.table_selected.connect(self.table_selected.emit)
        self.main_window.exit_requested.connect(self.exit_requested.emit)
        self.exit_requested.connect(self.close)

        # Set window properties
        self.setWindowTitle("PinballUX")
        # Enable frameless fullscreen mode
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Position on primary display initially
        self._position_main_window()

        # Set fullscreen mode
        self.showFullScreen()

        self.logger.info("PinballUX application initialized")

    def _position_main_window(self):
        """Position the main window on the configured playfield display"""
        if self.config.displays.playfield:
            # Use configured playfield monitor - resolve screen and geometry through monitor manager
            self.target_screen, x, y, width, height = self.monitor_manager._resolve_monitor_geometry(
                self.config.displays.playfield
            )

            # Set initial geometry
            screen_geom = self.target_screen.geometry()
            self.setGeometry(screen_geom.x(), screen_geom.y(), screen_geom.width(), screen_geom.height())
        else:
            # Use primary screen
            self.target_screen = None
            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.geometry()
                self.setGeometry(geometry)

    def showEvent(self, event):
        """Handle show event - move window to target screen"""
        super().showEvent(event)

        # Move to target screen after the window is shown
        if hasattr(self, 'target_screen') and self.target_screen:
            # Get the screen geometry
            screen_geom = self.target_screen.geometry()

            self.logger.info(
                f"Moving Playfield to screen at "
                f"({screen_geom.x()}, {screen_geom.y()}) {screen_geom.width()}x{screen_geom.height()}"
            )

            # Move window to the target screen's position
            self.move(screen_geom.x(), screen_geom.y())
            self.resize(screen_geom.width(), screen_geom.height())

            # Force window to be on correct screen via windowHandle if available
            if self.windowHandle():
                self.windowHandle().setScreen(self.target_screen)

    def show(self):
        """Show the application and all display windows"""
        super().show()

        # Show additional displays if configured
        if self.monitor_manager:
            self.monitor_manager.show_displays()

        self.logger.info("PinballUX application shown")

    def closeEvent(self, event):
        """Handle application close event"""
        self.logger.info("PinballUX application closing")

        # Close all display windows
        if self.monitor_manager:
            self.monitor_manager.close_displays()

        # Save configuration
        self.config.save()

        # Accept the close event
        event.accept()

    def keyPressEvent(self, event):
        """Handle key press events"""
        self.logger.debug(f"PinballUXApp keyPressEvent: {event.key()}")

        # Exit on escape key
        if event.key() == Qt.Key.Key_Escape:
            self.exit_requested.emit()
        else:
            # Forward to main window
            if self.main_window:
                self.main_window.keyPressEvent(event)