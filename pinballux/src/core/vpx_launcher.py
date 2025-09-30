"""
VPX table launcher for Visual Pinball Standalone integration
"""

import os
import subprocess
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)


class VPXLauncher(QObject):
    """Launcher for Visual Pinball Standalone tables"""

    # Signals
    table_launched = pyqtSignal(str)  # table_path
    table_exited = pyqtSignal(str, int, int)  # table_path, exit_code, duration_seconds
    table_crashed = pyqtSignal(str, str)  # table_path, error_message
    launch_failed = pyqtSignal(str, str)  # table_path, error_message

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.logger = get_logger(__name__)

        # Current process state
        self.current_process: Optional[QProcess] = None
        self.current_table_path: Optional[str] = None
        self.launch_time: Optional[datetime] = None

        # Process monitoring
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_process)

    def launch_table(self, table_path: str, options: Dict[str, Any] = None) -> bool:
        """Launch a VPX table with Visual Pinball Standalone"""
        try:
            # Check if a table is already running
            if self.is_table_running():
                self.logger.warning("A table is already running")
                return False

            # Validate table file exists
            if not os.path.exists(table_path):
                error_msg = f"Table file not found: {table_path}"
                self.logger.error(error_msg)
                self.launch_failed.emit(table_path, error_msg)
                return False

            # Get VP Standalone executable path
            vp_executable = self._get_vp_executable()
            if not vp_executable:
                error_msg = "Visual Pinball Standalone executable not found"
                self.logger.error(error_msg)
                self.launch_failed.emit(table_path, error_msg)
                return False

            # Build command line arguments
            command_args = self._build_command_args(table_path, options or {})

            self.logger.info(f"Launching table: {table_path}")
            self.logger.debug(f"Command: {vp_executable} {' '.join(command_args)}")

            # Create QProcess for better integration with Qt
            self.current_process = QProcess()
            self.current_process.finished.connect(self._on_process_finished)
            self.current_process.errorOccurred.connect(self._on_process_error)

            # Set working directory to VP executable directory
            vp_dir = str(Path(vp_executable).parent)
            self.current_process.setWorkingDirectory(vp_dir)

            # Start the process
            self.current_process.start(vp_executable, command_args)

            if not self.current_process.waitForStarted(5000):  # 5 second timeout
                error_msg = f"Failed to start Visual Pinball: {self.current_process.errorString()}"
                self.logger.error(error_msg)
                self.launch_failed.emit(table_path, error_msg)
                self.current_process = None
                return False

            # Track launch state
            self.current_table_path = table_path
            self.launch_time = datetime.now()

            # Start monitoring
            self.monitor_timer.start(1000)  # Check every second

            self.logger.info(f"Table launched successfully: {Path(table_path).name}")
            self.table_launched.emit(table_path)
            return True

        except Exception as e:
            error_msg = f"Failed to launch table: {str(e)}"
            self.logger.error(error_msg)
            self.launch_failed.emit(table_path, error_msg)
            return False

    def stop_table(self, force: bool = False) -> bool:
        """Stop the currently running table"""
        if not self.is_table_running():
            return True

        try:
            self.logger.info("Stopping current table")

            if force:
                # Force kill the process
                self.current_process.kill()
            else:
                # Try graceful termination first
                self.current_process.terminate()

                # Wait for graceful exit
                if not self.current_process.waitForFinished(5000):  # 5 second timeout
                    self.logger.warning("Graceful termination failed, force killing process")
                    self.current_process.kill()

            return True

        except Exception as e:
            self.logger.error(f"Failed to stop table: {e}")
            return False

    def is_table_running(self) -> bool:
        """Check if a table is currently running"""
        return (self.current_process is not None and
                self.current_process.state() == QProcess.ProcessState.Running)

    def get_current_table(self) -> Optional[str]:
        """Get the path of the currently running table"""
        if self.is_table_running():
            return self.current_table_path
        return None

    def get_play_duration(self) -> int:
        """Get current play session duration in seconds"""
        if self.launch_time:
            return int((datetime.now() - self.launch_time).total_seconds())
        return 0

    def _get_vp_executable(self) -> Optional[str]:
        """Get the Visual Pinball Standalone executable path"""
        # Check config first
        if self.config.vpx.executable_path and os.path.exists(self.config.vpx.executable_path):
            return self.config.vpx.executable_path

        # Common locations to search
        search_paths = [
            # Your specified VP executable location
            "/home/keith/github/pinballUX/vpinball/VPinballX_GL",
            # From our cloned VP repository
            "/home/keith/github/vpinball/standalone/linux-x64/vpinball_standalone",
            # System paths
            "/usr/local/bin/vpinball_standalone",
            "/usr/bin/vpinball_standalone",
            # User's home directory
            str(Path.home() / "bin" / "vpinball_standalone"),
            str(Path.home() / "vpinball" / "vpinball_standalone"),
        ]

        for path in search_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                self.logger.info(f"Found VP Standalone executable: {path}")
                # Update config for future use
                self.config.vpx.executable_path = path
                self.config.save()
                return path

        self.logger.error("Visual Pinball Standalone executable not found")
        return None

    def _build_command_args(self, table_path: str, options: Dict[str, Any]) -> list:
        """Build command line arguments for VPinballX_GL"""
        args = []

        # Enable true fullscreen (unless explicitly disabled) - goes first
        if options.get('fullscreen', True):
            args.append('-EnableTrueFullscreen')

        # VPinballX_GL specific arguments - Play comes after fullscreen
        args.append('-Play')

        # Additional VPinballX_GL options if available
        if options.get('disable_sound', False):
            args.append('-NoSound')

        if options.get('debug', False):
            args.append('-Debug')

        # The table file should be the last argument
        args.append(table_path)

        return args

    def _monitor_process(self):
        """Monitor the running process"""
        if not self.is_table_running():
            self.monitor_timer.stop()
            return

        # Check if process is still responding
        # This is a placeholder for more sophisticated monitoring
        # We could check CPU usage, memory, etc.
        pass

    def _on_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process finished signal"""
        self.monitor_timer.stop()

        table_path = self.current_table_path
        duration = self.get_play_duration()

        # Clean up state
        self.current_process = None
        self.current_table_path = None
        self.launch_time = None

        if exit_status == QProcess.ExitStatus.NormalExit:
            self.logger.info(f"Table exited normally with code {exit_code}, duration: {duration}s")
            self.table_exited.emit(table_path, exit_code, duration)
        else:
            self.logger.warning(f"Table crashed with code {exit_code}, duration: {duration}s")
            self.table_crashed.emit(table_path, f"Process crashed with exit code {exit_code}")

    def _on_process_error(self, error: QProcess.ProcessError):
        """Handle process error signal"""
        self.monitor_timer.stop()

        table_path = self.current_table_path
        error_messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start Visual Pinball",
            QProcess.ProcessError.Crashed: "Visual Pinball crashed",
            QProcess.ProcessError.Timedout: "Visual Pinball timed out",
            QProcess.ProcessError.ReadError: "Read error from Visual Pinball",
            QProcess.ProcessError.WriteError: "Write error to Visual Pinball",
            QProcess.ProcessError.UnknownError: "Unknown error with Visual Pinball"
        }

        error_msg = error_messages.get(error, f"Process error: {error}")
        self.logger.error(error_msg)

        # Clean up state
        self.current_process = None
        self.current_table_path = None
        self.launch_time = None

        if table_path:
            self.table_crashed.emit(table_path, error_msg)


class LaunchManager:
    """High-level manager for table launching and session tracking"""

    def __init__(self, config: Config, table_service=None):
        self.config = config
        self.table_service = table_service
        self.launcher = VPXLauncher(config)
        self.logger = get_logger(__name__)

        # Connect signals
        self.launcher.table_launched.connect(self._on_table_launched)
        self.launcher.table_exited.connect(self._on_table_exited)
        self.launcher.table_crashed.connect(self._on_table_crashed)
        self.launcher.launch_failed.connect(self._on_launch_failed)

        # Session tracking
        self.current_session_table_id: Optional[int] = None

    def launch_table_by_path(self, table_path: str, options: Dict[str, Any] = None) -> bool:
        """Launch table by file path"""
        return self.launcher.launch_table(table_path, options)

    def launch_table_by_id(self, table_id: int, options: Dict[str, Any] = None) -> bool:
        """Launch table by database ID"""
        if not self.table_service:
            self.logger.error("Table service not available")
            return False

        table = self.table_service.get_table_by_id(table_id)
        if not table:
            self.logger.error(f"Table not found with ID: {table_id}")
            return False

        self.current_session_table_id = table_id
        return self.launcher.launch_table(table.file_path, options)

    def stop_current_table(self, force: bool = False) -> bool:
        """Stop the currently running table"""
        return self.launcher.stop_table(force)

    def is_table_running(self) -> bool:
        """Check if a table is currently running"""
        return self.launcher.is_table_running()

    def get_current_table_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently running table"""
        if not self.is_table_running():
            return None

        return {
            'table_path': self.launcher.get_current_table(),
            'table_id': self.current_session_table_id,
            'duration': self.launcher.get_play_duration()
        }

    def _on_table_launched(self, table_path: str):
        """Handle table launched signal"""
        self.logger.info(f"Table launched: {Path(table_path).name}")

    def _on_table_exited(self, table_path: str, exit_code: int, duration: int):
        """Handle table exited signal"""
        self.logger.info(f"Table session ended: {Path(table_path).name}, duration: {duration}s")

        # Record play session in database
        if self.table_service and self.current_session_table_id and duration > 10:  # Only record sessions > 10 seconds
            self.table_service.record_table_play(self.current_session_table_id, duration)

        self.current_session_table_id = None

    def _on_table_crashed(self, table_path: str, error_message: str):
        """Handle table crashed signal"""
        self.logger.error(f"Table crashed: {Path(table_path).name} - {error_message}")
        self.current_session_table_id = None

    def _on_launch_failed(self, table_path: str, error_message: str):
        """Handle launch failed signal"""
        self.logger.error(f"Failed to launch table: {Path(table_path).name} - {error_message}")
        self.current_session_table_id = None