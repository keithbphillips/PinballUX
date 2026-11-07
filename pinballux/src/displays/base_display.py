"""
Base display class for all monitor displays
"""

from abc import ABC, abstractmethod
from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt6.QtGui import QPixmap, QPalette

from ..core.config import MonitorConfig
from ..core.logger import get_logger
from ..ui.media_widgets import TableMediaWidget


class BaseDisplay(QWidget):
    """Base class for all display windows"""

    # Signals
    content_updated = pyqtSignal(dict)
    display_clicked = pyqtSignal()

    def __init__(self, monitor_config: MonitorConfig, target_screen=None):
        super().__init__()
        self.monitor_config = monitor_config
        self.target_screen = target_screen
        self.logger = get_logger(__name__)

        self._setup_window()
        self._setup_layout()

    def _setup_window(self):
        """Set up window properties"""
        self.setWindowTitle(f"PinballUX - {self.monitor_config.name}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        # Set black background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.setPalette(palette)

        # Apply rotation if specified
        if self.monitor_config.rotation != 0:
            self._apply_rotation()

    def _target_geometry(self) -> Optional[QRect]:
        """Window geometry: the configured x/y/width/height when use_custom_geometry is on
        (lets several displays share one screen), otherwise the whole target screen."""
        mc = self.monitor_config
        if getattr(mc, 'use_custom_geometry', False) and None not in (mc.x, mc.y, mc.width, mc.height) \
                and mc.width > 0 and mc.height > 0:
            return QRect(mc.x, mc.y, mc.width, mc.height)
        if self.target_screen:
            return self.target_screen.geometry()
        return None

    def _apply_geometry(self):
        geom = self._target_geometry()
        if geom is None:
            return
        # Assign the screen first, then the geometry (setScreen can move the window)
        if self.windowHandle() and self.target_screen:
            self.windowHandle().setScreen(self.target_screen)
        self.setGeometry(geom)

    def showEvent(self, event):
        """Handle show event - move window to its target screen/geometry"""
        super().showEvent(event)

        geom = self._target_geometry()
        if geom is None:
            return
        self.logger.info(
            f"Placing {self.monitor_config.name} at ({geom.x()}, {geom.y()}) {geom.width()}x{geom.height()}"
            f"{' (custom geometry)' if getattr(self.monitor_config, 'use_custom_geometry', False) else ''}"
        )
        self._apply_geometry()
        # X11 window managers may reposition a window right after mapping it - apply once more
        QTimer.singleShot(0, self._apply_geometry)

    def _apply_rotation(self):
        """Apply rotation transformation to the display"""
        # This would need platform-specific implementation
        # For now, just log the rotation setting
        self.logger.info(f"Display rotation set to {self.monitor_config.rotation} degrees")

    @abstractmethod
    def _setup_layout(self):
        """Set up the display layout - must be implemented by subclasses"""
        pass

    @abstractmethod
    def update_content(self, content_data: dict):
        """Update display content - must be implemented by subclasses"""
        pass

    def show_image(self, image_path: str, label_widget: QLabel):
        """Helper method to show an image in a label widget"""
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale to fit the label while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    label_widget.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                label_widget.setPixmap(scaled_pixmap)
            else:
                self.logger.warning(f"Failed to load image: {image_path}")
        except Exception as e:
            self.logger.error(f"Error displaying image {image_path}: {e}")

    def load_media(self, media_widget: TableMediaWidget, media_path: str):
        """Helper method to load media into a media widget"""
        try:
            if media_widget and media_path:
                success = media_widget.load_media(media_path)
                if success:
                    self.logger.info(f"Loaded media: {media_path}")
                else:
                    self.logger.warning(f"Failed to load media: {media_path}")
                return success
        except Exception as e:
            self.logger.error(f"Error loading media {media_path}: {e}")
        return False

    def clear_content(self):
        """Clear all content from the display"""
        # Default implementation - can be overridden
        for child in self.findChildren(QLabel):
            child.clear()

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.display_clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Exit on escape
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)