"""
Backglass display component for pinball cabinet backglass monitor
"""

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont

from ..core.config import MonitorConfig
from .base_display import BaseDisplay
from ..ui.media_widgets import VideoWidget


class BackglassDisplay(BaseDisplay):
    """Display window for animated backglass artwork"""

    # Signals
    backglass_updated = pyqtSignal(str)  # image path

    def __init__(self, monitor_config: MonitorConfig):
        super().__init__(monitor_config)

        # Current content
        self.current_table = None
        self.current_image = None
        self.current_video = None
        self.current_media_type = None  # 'image' or 'video'

        # Animation timer for future animated backglass support
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)

    def _setup_layout(self):
        """Set up the backglass display layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main backglass image area
        self.backglass_label = QLabel()
        self.backglass_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.backglass_label.setStyleSheet("background-color: black; color: white;")
        self.backglass_label.setScaledContents(True)
        layout.addWidget(self.backglass_label, 1)

        # Video widget for backglass videos
        self.video_widget = VideoWidget(self)
        self.video_widget.hide()  # Initially hidden
        layout.addWidget(self.video_widget, 1)

        # Optional info area at bottom (can be hidden)
        self.info_layout = QHBoxLayout()
        self.info_layout.setContentsMargins(10, 5, 10, 5)

        # Table name
        self.table_name_label = QLabel("PinballUX")
        self.table_name_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        self.table_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Manufacturer/year
        self.table_info_label = QLabel("")
        self.table_info_label.setStyleSheet("color: #cccccc; font-size: 18px;")
        self.table_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.info_layout.addWidget(self.table_name_label)
        self.info_layout.addStretch()
        self.info_layout.addWidget(self.table_info_label)

        layout.addLayout(self.info_layout)

        # Set default content
        self._show_default_content()

    def update_content(self, content_data: dict):
        """Update backglass content"""
        table_name = content_data.get('table_name', 'Unknown Table')
        manufacturer = content_data.get('manufacturer', '')
        year = content_data.get('year', '')
        backglass_video = content_data.get('backglass_video', '')
        backglass_image = content_data.get('backglass_image', '')

        # Update table info
        self.table_name_label.setText(table_name)

        info_text = []
        if manufacturer:
            info_text.append(manufacturer)
        if year:
            info_text.append(str(year))
        self.table_info_label.setText(" • ".join(info_text))

        # Prefer video over image
        if backglass_video:
            self._display_backglass_video(backglass_video)
            self.current_video = backglass_video
            self.backglass_updated.emit(backglass_video)
        elif backglass_image:
            self._display_backglass_image(backglass_image)
            self.current_image = backglass_image
            self.backglass_updated.emit(backglass_image)
        else:
            self._show_default_content()

        self.current_table = content_data

    def _display_backglass_video(self, video_path: str):
        """Display backglass video"""
        try:
            # Stop current video if playing
            if self.video_widget.is_playing():
                self.video_widget.stop()

            # Hide image, show video
            self.backglass_label.hide()
            self.video_widget.show()

            # Load and play video
            if self.video_widget.load_video(video_path):
                self.video_widget.play()
                self.video_widget.set_muted(False)  # Play with audio

                # Loop video
                self.video_widget.playback_finished.connect(lambda: self.video_widget.play())

                self.current_media_type = 'video'
                self.logger.info(f"Loaded backglass video: {video_path}")
            else:
                self.logger.error(f"Failed to load backglass video: {video_path}")
                self._show_default_content()
        except Exception as e:
            self.logger.error(f"Failed to display backglass video {video_path}: {e}")
            self._show_default_content()

    def _display_backglass_image(self, image_path: str):
        """Display backglass image"""
        try:
            # Stop video if playing
            if self.video_widget.is_playing():
                self.video_widget.stop()
            self.video_widget.hide()

            # Show image
            self.backglass_label.show()
            self.backglass_label.clear()
            self.backglass_label.setStyleSheet("background-color: black;")

            # Load and display the image
            self.show_image(image_path, self.backglass_label)
            self.current_media_type = 'image'
            self.logger.info(f"Loaded backglass image: {image_path}")
        except Exception as e:
            self.logger.error(f"Failed to load backglass image {image_path}: {e}")
            self._show_default_content()

    def _show_default_content(self):
        """Show default content when no table is selected"""
        # Stop video if playing
        if self.video_widget.is_playing():
            self.video_widget.stop()
        self.video_widget.hide()

        # Show default label
        self.backglass_label.show()
        self.table_name_label.setText("PinballUX")
        self.table_info_label.setText("Visual Pinball Frontend")

        # Create a simple default background
        self.backglass_label.clear()
        self.backglass_label.setText("PinballUX\n\nReady to Play")
        self.backglass_label.setStyleSheet(
            "background-color: #1a1a2e; color: #eee; "
            "font-size: 48px; font-weight: bold; "
            "border: 2px solid #16213e;"
        )
        self.current_media_type = None

    def show_table_info(self, visible: bool = True):
        """Show or hide the table info area"""
        for i in range(self.info_layout.count()):
            widget = self.info_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(visible)

    def start_attract_mode(self, interval: int = 5000):
        """Start attract mode animation (for future use)"""
        self.animation_timer.start(interval)

    def stop_attract_mode(self):
        """Stop attract mode animation"""
        self.animation_timer.stop()

    def _update_animation(self):
        """Update animation frame (placeholder for future animated backglass)"""
        # Future: cycle through backglass frames or videos
        pass

    def clear_content(self):
        """Clear backglass content"""
        super().clear_content()
        if self.video_widget.is_playing():
            self.video_widget.stop()
        self._show_default_content()
        self.current_table = None
        self.current_image = None
        self.current_video = None