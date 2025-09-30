"""
Base display class for all monitor displays
"""

from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPalette

from ..core.config import MonitorConfig
from ..core.logger import get_logger
from ..ui.media_widgets import TableMediaWidget


class BaseDisplay(QWidget):
    """Base class for all display windows"""

    # Signals
    content_updated = pyqtSignal(dict)
    display_clicked = pyqtSignal()

    def __init__(self, monitor_config: MonitorConfig):
        super().__init__()
        self.monitor_config = monitor_config
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