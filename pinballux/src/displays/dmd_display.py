"""
DMD (Dot Matrix Display) component for pinball cabinet DMD monitor
"""

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt6.QtGui import QPixmap, QFont, QPainter, QBrush, QColor, QPen

from ..core.config import MonitorConfig
from .base_display import BaseDisplay
from ..ui.media_widgets import VideoWidget


class DMDDisplay(BaseDisplay):
    """Display window for DMD (Dot Matrix Display) simulation"""

    # Signals
    dmd_updated = pyqtSignal(str)  # status or content

    def __init__(self, monitor_config: MonitorConfig, target_screen=None, is_full_dmd: bool = False):
        # DMD properties - initialize before calling super()
        self.is_full_dmd = is_full_dmd
        self.dot_size = 3 if is_full_dmd else 2
        self.dot_spacing = 1
        self.dmd_width = 128  # Standard DMD width in dots
        self.dmd_height = 32  # Standard DMD height in dots
        self.current_message = "PinballUX Ready"
        self.scroll_position = 0
        self.current_media_type = None  # 'video', 'image', or 'text'

        # Get display mode from config (native or full)
        self.dmd_display_mode = monitor_config.dmd_mode if hasattr(monitor_config, 'dmd_mode') else "full"

        super().__init__(monitor_config, target_screen=target_screen)

        # Animation timer for scrolling text and effects
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_speed = 100  # milliseconds

    def _setup_layout(self):
        """Set up the DMD display layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # DMD frame with border
        self.dmd_frame = QFrame()
        self.dmd_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.dmd_frame.setLineWidth(2)
        self.dmd_frame.setStyleSheet(
            "QFrame { "
            "background-color: #000000; "
            "border: 2px solid #333333; "
            "border-radius: 5px; "
            "}"
        )

        # DMD content area
        frame_layout = QVBoxLayout(self.dmd_frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)

        # Main DMD display area (for text and images)
        self.dmd_label = QLabel()
        self.dmd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dmd_label.setStyleSheet(
            "background-color: #000000; "
            "color: #ff8800; "
            f"font-family: monospace; "
            f"font-size: {'24px' if self.is_full_dmd else '16px'}; "
            "font-weight: bold; "
            "border: 1px solid #444444;"
        )

        # Set sizing based on display mode
        if self.dmd_display_mode == "native":
            # Native mode: fixed size based on DMD dimensions
            self.dmd_label.setFixedSize(
                self.dmd_width * (self.dot_size + self.dot_spacing),
                self.dmd_height * (self.dot_size + self.dot_spacing)
            )
            self.dmd_label.setScaledContents(False)
        else:
            # Full mode: expand to fill available space
            self.dmd_label.setScaledContents(True)
            # Set size policy to expand
            from PyQt6.QtWidgets import QSizePolicy
            self.dmd_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        frame_layout.addWidget(self.dmd_label, 1)  # stretch factor 1 to expand

        # Video widget for DMD videos
        self.video_widget = VideoWidget(self)
        self.video_widget.hide()  # Initially hidden
        # Set sizing based on display mode
        if self.dmd_display_mode == "native":
            # Native mode: fixed size
            self.video_widget.setFixedSize(
                self.dmd_width * 4,  # 512px wide for 128-dot DMD
                self.dmd_height * 4   # 128px high for 32-dot DMD
            )
        else:
            # Full mode: expand to fill available space
            from PyQt6.QtWidgets import QSizePolicy
            self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame_layout.addWidget(self.video_widget, 1)  # stretch factor 1 to expand

        # Status bar for full DMD
        if self.is_full_dmd:
            self.status_layout = QHBoxLayout()

            self.score_label = QLabel("SCORE: 0")
            self.score_label.setStyleSheet("color: #ff8800; font-size: 14px; font-weight: bold;")

            self.ball_label = QLabel("BALL: 1")
            self.ball_label.setStyleSheet("color: #ff8800; font-size: 14px; font-weight: bold;")

            self.player_label = QLabel("PLAYER: 1")
            self.player_label.setStyleSheet("color: #ff8800; font-size: 14px; font-weight: bold;")

            self.status_layout.addWidget(self.score_label)
            self.status_layout.addStretch()
            self.status_layout.addWidget(self.ball_label)
            self.status_layout.addStretch()
            self.status_layout.addWidget(self.player_label)

            frame_layout.addLayout(self.status_layout)

        layout.addWidget(self.dmd_frame)

        # Set initial content
        self._show_default_content()

    def update_content(self, content_data: dict):
        """Update DMD content"""
        message = content_data.get('message', 'PinballUX')
        score = content_data.get('score', 0)
        ball = content_data.get('ball', 1)
        player = content_data.get('player', 1)
        animation = content_data.get('animation', False)
        dmd_video = content_data.get('dmd_video', '')
        dmd_image = content_data.get('dmd_image', '')

        # Prefer video over image over text
        if dmd_video:
            self._display_video(dmd_video)
        elif dmd_image:
            self._display_image(dmd_image)
        else:
            # Update main message
            self.current_message = message
            self._display_message(message)

        # Update status for full DMD
        if self.is_full_dmd:
            self.score_label.setText(f"SCORE: {score:,}")
            self.ball_label.setText(f"BALL: {ball}")
            self.player_label.setText(f"PLAYER: {player}")

        # Start/stop animation
        if animation and not self.animation_timer.isActive():
            self.start_animation()
        elif not animation and self.animation_timer.isActive():
            self.stop_animation()

        self.dmd_updated.emit(dmd_video if dmd_video else (dmd_image if dmd_image else message))

    def _display_video(self, video_path: str):
        """Display a video on the DMD"""
        try:
            # Stop current video if playing
            if self.video_widget.is_playing():
                self.video_widget.stop()

            # Hide label, show video
            self.dmd_label.hide()
            self.video_widget.show()

            # Configure scaling based on display mode
            if self.dmd_display_mode == "native":
                # Native mode: no scaling
                self.video_widget.scale_small_videos = False
            else:
                # Full mode: enable 2x scaling for small DMD videos
                self.video_widget.scale_small_videos = True
                self.video_widget.min_video_width = 512

            # Load and play video
            scale_enabled = self.dmd_display_mode == "full"
            if self.video_widget.load_video(video_path, scale_small_videos=scale_enabled, min_width=512 if scale_enabled else 0):
                self.video_widget.play()
                self.video_widget.set_muted(True)  # DMD videos typically silent

                # Loop video
                self.video_widget.playback_finished.connect(lambda: self.video_widget.play())

                self.current_media_type = 'video'
                self.logger.info(f"Loaded DMD video: {video_path}")
            else:
                self.logger.error(f"Failed to load DMD video: {video_path}")
                self._display_message("VIDEO LOAD ERROR")
        except Exception as e:
            self.logger.error(f"Failed to display DMD video {video_path}: {e}")
            self._display_message("VIDEO ERROR")

    def _display_image(self, image_path: str):
        """Display an image on the DMD"""
        try:
            # Stop video if playing
            if self.video_widget.is_playing():
                self.video_widget.stop()
            self.video_widget.hide()

            # Show label
            self.dmd_label.show()

            # Load image with nearest-neighbor scaling to prevent blur
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                if self.dmd_display_mode == "native":
                    # Native mode: no scaling, show at original size
                    self.dmd_label.setPixmap(pixmap)
                else:
                    # Full mode: scale to fit label size
                    # Use FastTransformation (nearest-neighbor) for sharp pixels
                    scaled_pixmap = pixmap.scaled(
                        self.dmd_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation
                    )
                    self.dmd_label.setPixmap(scaled_pixmap)
            else:
                self.logger.warning(f"Failed to load DMD image: {image_path}")
                self._display_message("IMAGE LOAD ERROR")
                return

            self.dmd_label.setStyleSheet(
                "background-color: #000000; "
                "border: 1px solid #444444;"
            )
            self.current_media_type = 'image'
            self.logger.info(f"Loaded DMD image: {image_path}")
        except Exception as e:
            self.logger.error(f"Failed to load DMD image {image_path}: {e}")
            self._display_message("IMAGE LOAD ERROR")

    def _display_message(self, message: str):
        """Display a message on the DMD"""
        # Stop video if playing
        if self.video_widget.is_playing():
            self.video_widget.stop()
        self.video_widget.hide()

        # Show label
        self.dmd_label.show()

        # Reset label to text display mode
        self.dmd_label.clear()
        self.dmd_label.setStyleSheet(
            "background-color: #000000; "
            "color: #ff8800; "
            f"font-family: monospace; "
            f"font-size: {'24px' if self.is_full_dmd else '16px'}; "
            "font-weight: bold; "
            "border: 1px solid #444444;"
        )

        # For simple implementation, just show the text
        # Future: implement proper dot matrix rendering
        display_text = message.upper()

        # If message is too long, it will scroll
        if len(display_text) > 16:  # Approximate characters that fit
            # This will be animated in _update_animation
            self.dmd_label.setText(display_text[:16] + "...")
        else:
            self.dmd_label.setText(display_text)

        self.current_media_type = 'text'

    def _show_default_content(self):
        """Show default DMD content"""
        self.current_message = "PINBALLUX READY"
        self._display_message(self.current_message)

        if self.is_full_dmd:
            self.score_label.setText("SCORE: 0")
            self.ball_label.setText("BALL: 1")
            self.player_label.setText("PLAYER: 1")

    def show_attract_mode(self):
        """Show attract mode on DMD"""
        attract_messages = [
            "PINBALLUX",
            "PRESS START",
            "SELECT TABLE",
            "READY TO PLAY"
        ]

        # Cycle through attract messages
        import random
        message = random.choice(attract_messages)
        self._display_message(message)

    def start_animation(self, speed: int = 100):
        """Start DMD animation (scrolling text, effects)"""
        self.animation_speed = speed
        self.scroll_position = 0
        self.animation_timer.start(self.animation_speed)

    def stop_animation(self):
        """Stop DMD animation"""
        self.animation_timer.stop()
        self.scroll_position = 0

    def _update_animation(self):
        """Update animation frame"""
        if len(self.current_message) > 16:
            # Scroll long messages
            self.scroll_position += 1
            if self.scroll_position > len(self.current_message):
                self.scroll_position = 0

            # Display scrolled portion
            start_pos = self.scroll_position
            display_text = (self.current_message + "   " + self.current_message)[start_pos:start_pos + 16]
            self.dmd_label.setText(display_text.upper())

    def flash_message(self, message: str, duration: int = 2000):
        """Flash a temporary message on the DMD"""
        original_message = self.current_message
        self._display_message(message)

        # Restore original message after duration
        QTimer.singleShot(duration, lambda: self._display_message(original_message))

    def clear_content(self):
        """Clear DMD content"""
        super().clear_content()
        if self.video_widget.is_playing():
            self.video_widget.stop()
        self._show_default_content()
        self.stop_animation()