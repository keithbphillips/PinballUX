#!/usr/bin/env python3
"""
Single Instance Lock - Ensures only one instance of PinballUX runs at a time
"""

import fcntl
import logging
import os
from pathlib import Path


class SingleInstanceLock:
    """
    Ensures only one instance of the application can run at a time.

    Uses an flock() on a lock file. The kernel drops the lock when the process
    exits for any reason (including a crash or SIGKILL), so a crashed instance
    can never block the next start. (The previous QSharedMemory approach could
    leave a stale System V segment behind after a crash on Linux.)
    """

    def __init__(self, app_name: str = "PinballUX", lock_dir: str = None):
        """
        Initialize the single instance lock.

        Args:
            app_name: Name of the application (used for the lock file name)
            lock_dir: Directory for the lock file (default: ~/.config/pinballux)
        """
        self.app_name = app_name
        self.logger = logging.getLogger(__name__)
        directory = Path(lock_dir) if lock_dir else Path.home() / ".config" / "pinballux"
        directory.mkdir(parents=True, exist_ok=True)
        self.lock_path = directory / f"{app_name.lower()}.lock"
        self._fd = None

    def acquire(self) -> bool:
        """
        Attempt to acquire the single instance lock.

        Returns:
            True if lock was acquired successfully, False if another instance is running
        """
        if self._fd is not None:
            return True
        try:
            fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError as e:
            self.logger.error(f"Failed to open lock file {self.lock_path}: {e}")
            return False

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            self.logger.warning(f"Another instance of {self.app_name} is already running")
            return False
        except OSError as e:
            os.close(fd)
            self.logger.error(f"Failed to acquire single instance lock: {e}")
            return False

        # Record our PID for troubleshooting (informational only)
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        self._fd = fd
        self.logger.info(f"Single instance lock acquired for {self.app_name}")
        return True

    def release(self):
        """
        Release the single instance lock.
        Called automatically on application exit.
        """
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
            self.logger.info(f"Single instance lock released for {self.app_name}")

    def __enter__(self):
        """Context manager entry"""
        if not self.acquire():
            raise RuntimeError(f"Another instance of {self.app_name} is already running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()

    def __del__(self):
        """Cleanup on deletion"""
        self.release()
