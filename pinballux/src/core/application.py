"""
Main application class for PinballUX
"""

import sys
from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QCoreApplication
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

        # Set window properties early
        self.setWindowTitle("PinballUX")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Show a simple black screen immediately to be responsive
        self._show_loading_screen()

        # Defer heavy initialization until after event loop starts
        QTimer.singleShot(0, self._setup_application)

    def _show_loading_screen(self):
        """Show a simple loading screen while initializing"""
        loading_widget = QWidget()
        loading_widget.setStyleSheet("background-color: #1a1a1a;")
        loading_layout = QVBoxLayout(loading_widget)
        loading_layout.setContentsMargins(50, 50, 50, 50)

        # Title
        title_label = QLabel("PinballUX")
        title_label.setStyleSheet("color: #4ecdc4; font-size: 48px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(title_label)

        loading_layout.addSpacing(20)

        # Loading message
        loading_label = QLabel("Loading...")
        loading_label.setStyleSheet("color: white; font-size: 24px;")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_label)

        loading_layout.addSpacing(20)

        # Status message
        self.status_label = QLabel("Initializing application...")
        self.status_label.setStyleSheet("color: #999; font-size: 16px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.status_label)

        self.setCentralWidget(loading_widget)

    def _setup_application(self):
        """Set up the main application"""
        self.logger.info("Initializing PinballUX application")

        try:
            # Initialize database
            self._update_loading_status("Initializing database...")
            self.database_manager = DatabaseManager()
            self.database_manager.initialize()

            # Initialize media manager
            self._update_loading_status("Initializing media manager...")
            self.media_manager = MediaManager(self.config)

            # Initialize table service with media manager
            self._update_loading_status("Loading table service...")
            self.table_service = TableService(self.database_manager, self.media_manager)

            # Initialize launch manager
            self._update_loading_status("Initializing launch manager...")
            self.launch_manager = LaunchManager(self.config, self.table_service)

            # Initialize monitor manager
            self._update_loading_status("Configuring displays...")
            self.monitor_manager = MonitorManager(self.config)

            # Show additional displays BEFORE creating wheel window so they're ready to receive content
            if self.monitor_manager:
                self.monitor_manager.show_displays()

            # Set up the main window (wheel interface)
            # This will load tables and emit table_highlighted signal, so displays must exist first
            self._update_loading_status("Loading table library...")
            self.main_window = WheelMainWindow(self.config, self.monitor_manager, self.table_service, self.launch_manager)
            self.setCentralWidget(self.main_window)

            # Connect signals
            self.main_window.table_selected.connect(self.table_selected.emit)
            self.main_window.exit_requested.connect(self.exit_requested.emit)
            self.exit_requested.connect(self.close)

            # Position on primary display initially
            self._position_main_window()

            # Set fullscreen mode
            self.showFullScreen()

            self.logger.info("PinballUX application initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}", exc_info=True)
            self._show_error_screen(str(e))

    def _update_loading_status(self, message: str):
        """Update loading screen status message"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            # Process events to update UI
            QApplication.processEvents()

    def _show_error_screen(self, error_message: str):
        """Show error screen if initialization fails"""
        error_widget = QWidget()
        error_widget.setStyleSheet("background-color: #1a1a1a;")
        error_layout = QVBoxLayout(error_widget)
        error_layout.setContentsMargins(50, 50, 50, 50)

        # Error title
        title_label = QLabel("Initialization Error")
        title_label.setStyleSheet("color: #ff6b6b; font-size: 32px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_layout.addWidget(title_label)

        error_layout.addSpacing(20)

        # Error message
        error_label = QLabel(error_message)
        error_label.setStyleSheet("color: white; font-size: 16px;")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setWordWrap(True)
        error_layout.addWidget(error_label)

        error_layout.addSpacing(20)

        # Instructions
        instruction_label = QLabel("Press ESC to exit\nCheck logs for details")
        instruction_label.setStyleSheet("color: #999; font-size: 14px;")
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_layout.addWidget(instruction_label)

        self.setCentralWidget(error_widget)

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

        # Note: Additional displays shown in _setup_application after initialization

        self.logger.info("PinballUX application shown")

    def closeEvent(self, event):
        """Handle application close event"""
        self.logger.info("PinballUX application closing")

        # Prevent re-entry during close
        if hasattr(self, '_closing'):
            self.logger.debug("Already closing, accepting event immediately")
            event.accept()
            return

        self._closing = True

        try:
            # Clean up main window first (contains media players and timers)
            if self.main_window:
                try:
                    self.logger.debug("Closing main window...")
                    # Trigger cleanup by closing the main window widget
                    self.main_window.close()
                    self.logger.debug("Main window closed")
                except Exception as e:
                    self.logger.error(f"Error closing main window: {e}", exc_info=True)

            # Close all display windows
            if self.monitor_manager:
                self.logger.debug("Closing display windows...")
                self.monitor_manager.close_displays()
                self.logger.debug("Display windows closed")

            # Save configuration
            self.logger.debug("Saving configuration...")
            self.config.save()
            self.logger.debug("Configuration saved")

        except Exception as e:
            self.logger.error(f"Error during application close: {e}", exc_info=True)

        finally:
            # Always accept the close event
            self.logger.info("Close event accepted")
            event.accept()

            # Force quit the application after cleanup
            self.logger.debug("Calling QApplication.quit()...")
            QApplication.quit()

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