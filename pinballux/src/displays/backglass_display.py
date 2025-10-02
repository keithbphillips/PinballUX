"""
Backglass display component for pinball cabinet backglass monitor
"""

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QLinearGradient, QBrush, QPen, QPainterPath

from ..core.config import MonitorConfig
from .base_display import BaseDisplay
from ..ui.media_widgets import VideoWidget


class BackglassDisplay(BaseDisplay):
    """Display window for animated backglass artwork"""

    # Signals
    backglass_updated = pyqtSignal(str)  # image path

    def __init__(self, monitor_config: MonitorConfig, target_screen=None):
        super().__init__(monitor_config, target_screen=target_screen)

        # Current content
        self.current_table = None
        self.current_image = None
        self.current_video = None
        self.current_media_type = None  # 'image' or 'video'

        # Loading state
        self.is_loading = False
        self.loading_table_name = ""
        self.loading_spinner_index = 0
        self.loading_spinner_chars = ["⚡", "✦", "★", "✦"]
        self.loading_start_time = None
        self.min_loading_duration_ms = 2000  # Minimum 2 seconds
        self.pending_hide = False

        # Animation timer for future animated backglass support
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)

        # Loading animation timer
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self._update_loading_spinner)

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

        # Connect video looping once here, not every time a video loads
        self.video_widget.playback_finished.connect(self._on_video_finished)

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

        # Hide info area by default
        self.show_table_info(False)

        # Set default content
        self._show_default_content()

    def update_content(self, content_data: dict):
        """Update backglass content"""
        # Don't update content if we're showing the loading screen
        if self.is_loading:
            self.logger.warning(f"BLOCKED: Ignoring update_content because loading screen is active (is_loading={self.is_loading})")
            import traceback
            self.logger.debug(f"Call stack:\n{''.join(traceback.format_stack())}")
            return

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
        self.logger.info(f"_display_backglass_video called: {video_path}, is_loading={self.is_loading}")
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

                # Video looping is handled by _on_video_finished, connected in _setup_layout

                self.current_media_type = 'video'
                self.logger.info(f"Loaded backglass video: {video_path}")
            else:
                self.logger.error(f"Failed to load backglass video: {video_path}")
                self._show_default_content()
        except Exception as e:
            self.logger.error(f"Failed to display backglass video {video_path}: {e}")
            self._show_default_content()

    def _on_video_finished(self):
        """Handle video playback finished - loop the video"""
        if self.current_media_type == 'video' and not self.is_loading:
            # Restart the video for looping
            self.video_widget.play()

    def _display_backglass_image(self, image_path: str):
        """Display backglass image"""
        self.logger.info(f"_display_backglass_image called: {image_path}, is_loading={self.is_loading}")
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

    def show_loading(self, table_name: str):
        """Show loading screen for a table - replaces all backglass content"""
        from PyQt6.QtCore import QDateTime

        self.logger.info(f"BackglassDisplay: show_loading called for '{table_name}'")
        self.is_loading = True
        self.loading_table_name = table_name
        self.loading_spinner_index = 0
        self.loading_start_time = QDateTime.currentMSecsSinceEpoch()
        self.pending_hide = False

        # STOP and HIDE video completely
        if self.video_widget.is_playing():
            self.logger.debug("Stopping video playback")
            self.video_widget.stop()
        self.video_widget.hide()
        self.video_widget.setVisible(False)

        # Clear any pixmap from the label
        self.backglass_label.clear()
        self.backglass_label.setPixmap(QPixmap())  # Clear any image

        # Make absolutely sure the label is shown and raised to top
        self.backglass_label.setVisible(True)
        self.backglass_label.show()
        self.backglass_label.raise_()

        self.logger.debug(f"Backglass label visible: {self.backglass_label.isVisible()}, size: {self.backglass_label.size()}")

        # Start loading animation
        self.loading_timer.start(200)  # Update spinner every 200ms
        self._update_loading_display()

        # Force immediate update
        self.backglass_label.update()
        self.update()

        self.logger.info(f"Loading screen started at {self.loading_start_time}, will show for minimum {self.min_loading_duration_ms}ms")

    def hide_loading(self):
        """Hide loading screen - leave backglass blank during gameplay"""
        from PyQt6.QtCore import QDateTime

        self.logger.info("BackglassDisplay: hide_loading called")

        # Check if minimum display time has elapsed
        if self.loading_start_time is not None:
            elapsed = QDateTime.currentMSecsSinceEpoch() - self.loading_start_time
            self.logger.debug(f"Loading screen elapsed time: {elapsed}ms (min: {self.min_loading_duration_ms}ms)")

            if elapsed < self.min_loading_duration_ms:
                # Not enough time has passed, delay hiding
                remaining = self.min_loading_duration_ms - elapsed
                self.logger.info(f"Delaying hide_loading by {remaining}ms to meet minimum display time")
                self.pending_hide = True
                QTimer.singleShot(int(remaining), self._do_hide_loading)
                return

        # Minimum time has elapsed, hide immediately
        self._do_hide_loading()

    def _do_hide_loading(self):
        """Actually hide the loading screen"""
        self.logger.info("BackglassDisplay: _do_hide_loading - keeping loading screen visible, VPX will take over")
        self.is_loading = False
        self.loading_timer.stop()
        self.pending_hide = False
        self.loading_start_time = None

        # Keep the loading screen visible - VPX will use this display for its own backglass
        # We just stop the spinner animation but leave the text visible
        self.logger.debug("Loading screen animation stopped, display ready for VPX backglass")

    def _update_loading_spinner(self):
        """Update the loading spinner animation"""
        self.loading_spinner_index = (self.loading_spinner_index + 1) % len(self.loading_spinner_chars)
        self._update_loading_display()

    def _update_loading_display(self):
        """Update the loading display with current spinner"""
        spinner = self.loading_spinner_chars[self.loading_spinner_index]
        loading_text = f"{spinner}\n\nLOADING TABLE\n\n{self.loading_table_name}\n\n{spinner}"

        self.logger.debug(f"Updating loading display: spinner={spinner}, index={self.loading_spinner_index}")

        # Set the text
        self.backglass_label.setText(loading_text)

        # Apply styling
        self.backglass_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e,
                    stop:0.5 #16213e,
                    stop:1 #1a1a2e);
                color: #6496FF;
                font-size: 48px;
                font-weight: bold;
                border: 3px solid #6496FF;
                border-radius: 10px;
                padding: 40px;
            }
        """)

        # Make sure it's aligned center
        self.backglass_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Force update
        self.backglass_label.update()
        self.backglass_label.repaint()