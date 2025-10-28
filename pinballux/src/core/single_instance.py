#!/usr/bin/env python3
"""
Single Instance Lock - Ensures only one instance of PinballUX runs at a time
"""

import logging
from PyQt6.QtCore import QSharedMemory


class SingleInstanceLock:
    """
    Ensures only one instance of the application can run at a time.
    Uses QSharedMemory for cross-platform single-instance enforcement.
    """

    def __init__(self, app_name: str = "PinballUX"):
        """
        Initialize the single instance lock.

        Args:
            app_name: Name of the application (used for shared memory key)
        """
        self.app_name = app_name
        self.logger = logging.getLogger(__name__)
        self.shared_memory = QSharedMemory(app_name)

    def acquire(self) -> bool:
        """
        Attempt to acquire the single instance lock.

        Returns:
            True if lock was acquired successfully, False if another instance is running
        """
        # Try to attach to existing shared memory
        if self.shared_memory.attach():
            # Another instance is already running
            self.logger.warning(f"Another instance of {self.app_name} is already running")
            return False

        # Try to create new shared memory segment (1 byte is enough)
        if self.shared_memory.create(1):
            self.logger.info(f"Single instance lock acquired for {self.app_name}")
            return True

        # Failed to create or attach
        self.logger.error(f"Failed to acquire single instance lock: {self.shared_memory.errorString()}")
        return False

    def release(self):
        """
        Release the single instance lock.
        Called automatically on application exit.
        """
        if self.shared_memory.isAttached():
            self.shared_memory.detach()
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
