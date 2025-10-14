#!/usr/bin/env python3
"""
PinballUX - Main Application Entry Point
"""

import sys
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings, QtMsgType, qInstallMessageHandler
from PyQt6.QtGui import QIcon

# Add the pinballux directory to the Python path to fix imports
current_dir = os.path.dirname(os.path.abspath(__file__))
pinballux_dir = os.path.dirname(current_dir)
sys.path.insert(0, pinballux_dir)

# Handle both development and installed import paths
try:
    from pinballux.src.core.application import PinballUXApp
    from pinballux.src.core.config import Config
    from pinballux.src.core.logger import setup_logging
except ModuleNotFoundError:
    from src.core.application import PinballUXApp
    from src.core.config import Config
    from src.core.logger import setup_logging


def qt_message_handler(mode, context, message):
    """
    Custom Qt message handler to filter out harmless warnings.
    Suppresses libpng iCCP profile warnings that clutter the console.
    """
    # Filter out libpng iCCP warnings (harmless color profile warnings)
    if "libpng warning: iCCP" in message:
        return

    # Pass through other messages to default handler
    if mode == QtMsgType.QtDebugMsg:
        logging.debug(f"Qt: {message}")
    elif mode == QtMsgType.QtInfoMsg:
        logging.info(f"Qt: {message}")
    elif mode == QtMsgType.QtWarningMsg:
        logging.warning(f"Qt: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        logging.error(f"Qt: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        logging.critical(f"Qt: {message}")


def setup_vpinmame_roms_symlink():
    """
    Set up symlink from ~/.pinmame/roms to the project's roms directory.
    VPinMAME requires ROMs to be in ~/.pinmame/roms for proper operation.
    """
    logger = logging.getLogger(__name__)

    # Get the project roms directory
    project_root = Path(__file__).parent.parent
    roms_dir = project_root / "data" / "roms"

    # Ensure project roms directory exists (only if writable)
    try:
        roms_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.info(f"ROMs directory already exists at {roms_dir}")

    # Get the VPinMAME roms directory path
    vpinmame_dir = Path.home() / ".pinmame"
    vpinmame_roms = vpinmame_dir / "roms"

    # Create .pinmame directory if it doesn't exist
    vpinmame_dir.mkdir(parents=True, exist_ok=True)

    # Check if the symlink already exists and points to the correct location
    if vpinmame_roms.is_symlink():
        if vpinmame_roms.resolve() == roms_dir.resolve():
            logger.info(f"VPinMAME roms symlink already correctly configured: {vpinmame_roms} -> {roms_dir}")
            return
        else:
            logger.warning(f"VPinMAME roms symlink points to wrong location, removing: {vpinmame_roms}")
            vpinmame_roms.unlink()
    elif vpinmame_roms.exists():
        logger.warning(f"VPinMAME roms exists as directory/file, not symlink. Cannot proceed.")
        logger.warning(f"Please manually remove or rename: {vpinmame_roms}")
        return

    # Create the symlink
    try:
        vpinmame_roms.symlink_to(roms_dir, target_is_directory=True)
        logger.info(f"Created VPinMAME roms symlink: {vpinmame_roms} -> {roms_dir}")
    except Exception as e:
        logger.error(f"Failed to create VPinMAME roms symlink: {e}")


def main():
    """Main application entry point"""
    # Set up high DPI scaling (PyQt6 handles this automatically)
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

    # Install custom message handler to filter out harmless libpng warnings
    qInstallMessageHandler(qt_message_handler)

    # Create the Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("PinballUX")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("PinballUX")

    # Set up logging
    setup_logging()

    # Set up VPinMAME roms symlink
    setup_vpinmame_roms_symlink()

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