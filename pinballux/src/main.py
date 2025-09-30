#!/usr/bin/env python3
"""
PinballUX - Main Application Entry Point
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon

# Add the pinballux directory to the Python path to fix imports
current_dir = os.path.dirname(os.path.abspath(__file__))
pinballux_dir = os.path.dirname(current_dir)
sys.path.insert(0, pinballux_dir)

from pinballux.src.core.application import PinballUXApp
from pinballux.src.core.config import Config
from pinballux.src.core.logger import setup_logging


def main():
    """Main application entry point"""
    # Set up high DPI scaling (PyQt6 handles this automatically)
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

    # Create the Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("PinballUX")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("PinballUX")

    # Set up logging
    setup_logging()

    # Load configuration
    config = Config()

    # Create and run the main application
    pinball_app = PinballUXApp(config)

    # Show the application
    pinball_app.show()

    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()