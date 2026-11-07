"""
PinballX-style wheel widget for table selection
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsView, QGraphicsScene, QGraphicsOpacityEffect, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QSizeF, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QRect, pyqtProperty, QUrl
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QBrush, QLinearGradient, QPen, QPainterPath, QTransform
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem

from typing import List
from pathlib import Path

from ..core.logger import get_logger
from ..input.input_manager import InputManager, InputAction
from .media_widgets import AudioPlayer
from .wheel_canvas import WheelCanvas

logger = get_logger(__name__)


class LoadingPopup(QWidget):
    """Appealing popup window showing table loading status"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Set as a regular widget that will draw on top
        self.setAutoFillBackground(False)
        self.base_width = 600
        self.base_height = 300
        self.rotation_angle = 0
        self.table_name = ""
        self.spinner_index = 0
        self.spinner_chars = ["⚡", "✦", "★", "✦"]

        # Spinner timer
        self.spinner_timer = QTimer()
        self.spinner_timer.timeout.connect(self._update_spinner)

        # Opacity for fade animations
        self.opacity = 0.0

        # Initially hide
        self.hide()

    def _update_spinner(self):
        """Update spinner animation"""
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        self.update()  # Trigger repaint

    def paintEvent(self, event):
        """Custom paint event to draw the rotated loading popup"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Draw semi-transparent full-screen overlay first (for dimming effect)
        painter.setOpacity(self.opacity * 0.5)  # 50% of current opacity
        painter.fillRect(self.rect(), QColor(0, 0, 0, 180))

        # Reset opacity for the popup
        painter.setOpacity(self.opacity)

        # Apply rotation transform
        if self.rotation_angle != 0:
            center_x = self.width() / 2.0
            center_y = self.height() / 2.0
            painter.translate(center_x, center_y)
            painter.rotate(self.rotation_angle)
            painter.translate(-self.base_width / 2.0, -self.base_height / 2.0)
        else:
            # No rotation needed
            painter.translate((self.width() - self.base_width) / 2.0,
                            (self.height() - self.base_height) / 2.0)

        # Draw the popup container with gradient background
        rect = QRectF(0, 0, self.base_width, self.base_height)

        # Background gradient
        bg_gradient = QLinearGradient(0, 0, 0, self.base_height)
        bg_gradient.setColorAt(0, QColor(30, 30, 40, 240))
        bg_gradient.setColorAt(0.5, QColor(20, 20, 30, 240))
        bg_gradient.setColorAt(1, QColor(30, 30, 40, 240))

        # Draw rounded rectangle background
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)
        painter.fillPath(path, QBrush(bg_gradient))

        # Border gradient
        border_gradient = QLinearGradient(0, 0, self.base_width, 0)
        border_gradient.setColorAt(0, QColor(100, 150, 255, 200))
        border_gradient.setColorAt(0.5, QColor(150, 100, 255, 200))
        border_gradient.setColorAt(1, QColor(100, 150, 255, 200))

        # Draw border
        pen = QPen(QBrush(border_gradient), 3)
        painter.setPen(pen)
        painter.drawPath(path)

        # Draw spinner icon
        spinner_font = QFont("Arial", 72)
        painter.setFont(spinner_font)
        painter.setPen(QColor(100, 150, 255))
        spinner_rect = QRectF(0, 60, self.base_width, 80)
        painter.drawText(spinner_rect, Qt.AlignmentFlag.AlignCenter, self.spinner_chars[self.spinner_index])

        # Draw "LOADING TABLE" text
        loading_font = QFont("Arial", 36, QFont.Weight.Bold)
        painter.setFont(loading_font)
        painter.setPen(QColor(255, 255, 255))
        loading_rect = QRectF(0, 150, self.base_width, 50)
        painter.drawText(loading_rect, Qt.AlignmentFlag.AlignCenter, "LOADING TABLE")

        # Draw table name
        name_font = QFont("Arial", 24)
        painter.setFont(name_font)
        painter.setPen(QColor(200, 200, 255))
        name_rect = QRectF(40, 210, self.base_width - 80, 70)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.table_name)

        painter.end()

    def show_loading(self, table_name: str, rotation_angle: int = 0):
        """Show the loading popup with table name and rotation"""
        self.table_name = table_name
        self.rotation_angle = rotation_angle

        # Fill the entire parent window
        if self.parent():
            parent_rect = self.parent().rect()
            self.setGeometry(0, 0, parent_rect.width(), parent_rect.height())

        # Start animations
        self.show()
        self.raise_()

        # Animate opacity from 0 to 1
        self.opacity = 0.0
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self._fade_in_step)
        self.fade_timer.start(16)  # ~60fps

        self.spinner_timer.start(200)

    def _fade_in_step(self):
        """Gradually increase opacity for fade-in"""
        self.opacity = min(1.0, self.opacity + 0.05)
        self.update()
        if self.opacity >= 1.0:
            self.fade_timer.stop()

    def hide_loading(self):
        """Hide the loading popup with fade-out"""
        # Stop fade-in if running
        if hasattr(self, 'fade_timer'):
            self.fade_timer.stop()

        # Animate opacity from current value to 0
        self.fade_out_timer = QTimer()
        self.fade_out_timer.timeout.connect(self._fade_out_step)
        self.fade_out_timer.start(16)  # ~60fps

    def _fade_out_step(self):
        """Gradually decrease opacity for fade-out"""
        self.opacity = max(0.0, self.opacity - 0.05)
        self.update()
        if self.opacity <= 0.0:
            self.fade_out_timer.stop()
            self.spinner_timer.stop()
            self.hide()


class WheelWidget(QWidget):
    """PinballX-style wheel widget for table selection"""

    # Signals
    table_selected = pyqtSignal(dict)  # table_data
    table_highlighted = pyqtSignal(dict)  # table_data (emitted after delay when wheel stops)
    table_navigation = pyqtSignal()  # emitted immediately when wheel moves (for sound only)
    rotation_changed = pyqtSignal(int)  # rotation_angle

    INFO_HEIGHT = 156  # px, table info panel

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)

        # Wheel state
        self.tables = []
        self.current_index = 0
        self.is_animating = False

        # Delayed media update system
        self.media_update_timer = QTimer()
        self.media_update_timer.setSingleShot(True)
        self.media_update_timer.timeout.connect(self._delayed_media_update)
        self.media_update_delay = 500  # ms delay after animation stops (allows quick navigation)

        # Rotation system (like PinballX)
        self.rotation_angle = 0  # 0, 90, 180, 270 degrees
        self.rotation_angles = [0, 90, 180, 270]  # Available rotation angles
        self.rotation_index = 0  # Current index in rotation_angles

        # Set focus policy to receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setup_ui()

    def setup_ui(self):
        """Setup the wheel UI with proper layering"""
        # Set a default background color
        self.setStyleSheet("background-color: #1a1a1a;")
        self.setAutoFillBackground(True)

        # Create background video scene that fills the entire widget
        self.setup_background_video()

        # Create wheel container and embed it in the scene
        self.wheel_container = QWidget()
        # Don't set fixed height - let _update_scene_layout handle sizing dynamically
        self.wheel_container.setStyleSheet("""
            background-color: transparent;
        """)
        self.wheel_container.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.wheel_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # The whole wheel (stage, spotlight, logos) is painted by one canvas
        self.wheel_canvas = WheelCanvas(self.wheel_container)
        self.wheel_canvas.settled.connect(self._on_wheel_settled)

        self.wheel_proxy = self.background_scene.addWidget(self.wheel_container)
        self.wheel_proxy.setZValue(10)

        # Table info display embedded in the scene
        self.info_widget = QWidget()
        self.info_widget.setObjectName("infoPanel")
        self.info_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.info_widget.setFixedHeight(self.INFO_HEIGHT)
        # Scoped to #infoPanel so the border/radius don't cascade onto the labels inside
        self.info_widget.setStyleSheet("""
            #infoPanel {
                background-color: rgba(12, 15, 24, 0.82);
                border: 1px solid rgba(140, 190, 255, 0.22);
                border-radius: 22px;
            }
            #infoPanel QLabel { background: transparent; border: none; }
        """)
        self.info_proxy = self.background_scene.addWidget(self.info_widget)
        self.info_proxy.setZValue(20)
        self.setup_info_widget()

        # Initial geometry sync
        self._update_scene_layout()

    def setup_background_video(self):
        """Setup background video playback"""
        self.background_scene = QGraphicsScene(self)
        self.background_view = QGraphicsView(self.background_scene, self)
        self.background_view.setFrameShape(QFrame.Shape.NoFrame)
        self.background_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.background_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.background_view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.background_view.setStyleSheet("background-color: #1a1a1a; border: none;")

        # Create media player for background video
        self.background_media_player = QMediaPlayer()
        self.background_audio_output = QAudioOutput()
        self.background_audio_output.setVolume(0.2)  # 20% volume for background
        self.background_media_player.setAudioOutput(self.background_audio_output)

        # Graphics view video item
        self.background_video_item = QGraphicsVideoItem()
        self.background_video_item.setZValue(0)
        self.background_video_item.setVisible(False)
        self.background_scene.addItem(self.background_video_item)
        self.background_media_player.setVideoOutput(self.background_video_item)

        # Default fallback background widget (through proxy)
        self.default_background = QLabel()
        self.default_background.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_background.setStyleSheet("background-color: #1a1a1a; color: #555; font-size: 18px;")
        self.default_background.setText("No Table Video Available")
        self.default_background.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.default_background.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.default_background_proxy = self.background_scene.addWidget(self.default_background)
        self.default_background_proxy.setZValue(5)

        # Monitor playback events
        self.background_media_player.mediaStatusChanged.connect(self._on_background_media_status_changed)

    def setup_info_widget(self):
        """Setup the table information display"""
        layout = QVBoxLayout(self.info_widget)
        layout.setContentsMargins(36, 16, 36, 18)
        layout.setSpacing(2)

        # Table name
        self.table_name_label = QLabel("Select a Table")
        self.table_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_name_label.setStyleSheet(
            "font-family: 'Ubuntu Sans', 'Ubuntu', sans-serif; font-size: 40px; font-weight: 600;"
            " color: #f4f7fc; letter-spacing: 0.5px;")
        layout.addWidget(self.table_name_label)

        # Table info (manufacturer, year, play count)
        self.table_info_label = QLabel("")
        self.table_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_info_label.setStyleSheet(
            "font-family: 'Ubuntu Sans', 'Ubuntu', sans-serif; font-size: 23px; font-weight: 500;"
            " color: #8fc3ff; letter-spacing: 1px;")
        layout.addWidget(self.table_info_label)

        # Table metadata (theme, IPDB, players, author)
        self.table_metadata_label = QLabel("")
        self.table_metadata_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_metadata_label.setStyleSheet(
            "font-family: 'Ubuntu Sans', 'Ubuntu', sans-serif; font-size: 18px; color: #8b93a5;")
        self.table_metadata_label.setWordWrap(True)
        layout.addWidget(self.table_metadata_label)

    def set_tables(self, tables: List[dict]):
        """Set the tables for the wheel"""
        self.tables = tables
        self.current_index = 0
        self.wheel_canvas.set_tables(tables)
        self.update_wheel_display(animate=False)  # No animation on initial setup

    def update_wheel_display(self, animate=True):
        """Show the current table. Without animation the wheel jumps there and media loads now;
        animated moves go through _scroll()."""
        if not self.tables:
            return
        if animate:
            self._scroll(0)
            return
        if self.media_update_timer.isActive():
            self.media_update_timer.stop()
        self.wheel_canvas.jump_to(self.current_index)
        self.is_animating = False
        self.update_table_info()

    def _scroll(self, delta: int):
        """Animate the wheel by delta tables. Text updates now; heavy media once it settles."""
        if self.media_update_timer.isActive():
            self.media_update_timer.stop()
            self.logger.debug("Cancelled pending media update due to new wheel movement")
        self.table_navigation.emit()  # immediate sound feedback
        self.is_animating = True
        self.wheel_canvas.step(delta)
        self.update_table_info_text_only()

    def _on_wheel_settled(self, index: int):
        """Called when the wheel stops moving"""
        self.is_animating = False
        # Media only loads once the wheel has rested briefly (keeps fast scrolling smooth)
        self.media_update_timer.start(self.media_update_delay)

    def _delayed_media_update(self):
        """Update media after wheel has stopped moving"""
        self.logger.debug("Delayed media update triggered - loading heavy media now")

        # Update both text and media (playfield video/image)
        self.update_table_info()

        # Emit signal to update other displays (backglass, DMD) via WheelMainWindow
        # This will trigger on_table_highlighted with is_animating=False
        if self.tables and 0 <= self.current_index < len(self.tables):
            table = self.tables[self.current_index]
            self.table_highlighted.emit(table)

    def _on_background_media_status_changed(self, status):
        """Handle background media status changes for looping"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Restart the video for seamless looping
            self.background_media_player.setPosition(0)
            self.background_media_player.play()

    def play_background_video(self, video_path: str):
        """Play a background video for the selected table"""
        if not video_path or not Path(video_path).exists():
            # Stop any current video and show default background
            self.background_media_player.stop()
            self.background_media_player.setSource(QUrl())
            self.background_video_item.setVisible(False)
            self.default_background_proxy.setVisible(True)
            self.default_background.setText("No Media Available")
            return

        try:
            # Clear previous source before loading new video
            self.background_media_player.stop()
            self.background_media_player.setSource(QUrl())

            # Load and play the video
            self.background_media_player.setSource(QUrl.fromLocalFile(video_path))
            self.default_background_proxy.setVisible(False)
            self.background_video_item.setVisible(True)
            self.background_media_player.play()

            self.logger.debug(f"Playing background video: {Path(video_path).name}")

        except Exception as e:
            self.logger.error(f"Failed to play background video {video_path}: {e}")
            # Fall back to default background
            self.background_video_item.setVisible(False)
            self.default_background_proxy.setVisible(True)
            self.default_background.setText("Video Load Failed")

    def play_background_image(self, image_path: str):
        """Display a background image for the selected table"""
        if not image_path or not Path(image_path).exists():
            self.default_background_proxy.setVisible(True)
            self.default_background.setText("No Media Available")
            return

        try:
            # Stop video if playing and clear source
            self.background_media_player.stop()
            self.background_media_player.setSource(QUrl())
            self.background_video_item.setVisible(False)

            # Load and display the image in the default background label
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Use scene size or widget size for scaling
                target_size = self.background_view.size()
                if target_size.width() > 0 and target_size.height() > 0:
                    # Scale pixmap to fit while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        target_size,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                else:
                    scaled_pixmap = pixmap

                self.default_background.setPixmap(scaled_pixmap)
                self.default_background.setScaledContents(True)
                self.default_background_proxy.setVisible(True)

                # Apply rotation transform to the image proxy for 90° and 270° rotations
                self._apply_image_rotation()

                self.logger.debug(f"Displaying background image: {Path(image_path).name} (rotation: {self.rotation_angle}°)")
            else:
                self.default_background.clear()
                self.default_background.setText("Image Load Failed")
                self.default_background_proxy.setVisible(True)

        except Exception as e:
            self.logger.error(f"Failed to display background image {image_path}: {e}")
            self.default_background.clear()
            self.default_background.setText("Image Load Failed")
            self.default_background_proxy.setVisible(True)

    def stop_background_media(self):
        """Stop background video/image playback"""
        self.background_media_player.stop()
        self.background_media_player.setSource(QUrl())
        self.background_video_item.setVisible(False)
        self.default_background.clear()
        self.default_background_proxy.setVisible(True)
        self.default_background.setText("No Media Available")

    def stop_background_video(self):
        """Stop background video playback (legacy method)"""
        self.stop_background_media()

    def update_table_info_text_only(self):
        """Update only the table information text (no media loading)"""
        if not self.tables or self.current_index >= len(self.tables):
            self.table_name_label.setText("No Tables Available")
            self.table_info_label.setText("")
            self.table_metadata_label.setText("")
            return

        table = self.tables[self.current_index]

        # Table name
        table_name = table.get('name', 'Unknown Table')
        self.table_name_label.setText(table_name)

        # Basic table info (manufacturer, year, play count)
        manufacturer = table.get('manufacturer', '')
        year = table.get('year', '')
        play_count = table.get('play_count', 0)

        info_parts = []
        if manufacturer:
            info_parts.append(manufacturer)
        if year:
            info_parts.append(str(year))
        if play_count > 0:
            info_parts.append(f"Played {play_count} times")

        info_text = " • ".join(info_parts) if info_parts else ""
        self.table_info_label.setText(info_text)
        self.table_info_label.setVisible(bool(info_text))  # no empty gap in the panel

        # Table metadata (theme, IPDB, players, author)
        metadata_parts = []

        theme = table.get('theme', '')
        if theme:
            metadata_parts.append(f"Theme: {theme}")

        ipdb_number = table.get('ipdb_number', 0)
        if ipdb_number:
            metadata_parts.append(f"IPDB #{ipdb_number}")

        players = table.get('players', 0)
        if players and players > 1:
            metadata_parts.append(f"{players} Players")

        author = table.get('author', '')
        if author:
            # Truncate author if too long
            if len(author) > 40:
                author = author[:37] + "..."
            metadata_parts.append(f"By {author}")

        metadata_text = " • ".join(metadata_parts)
        self.table_metadata_label.setText(metadata_text)
        self.table_metadata_label.setVisible(bool(metadata_text))

    def update_table_info(self):
        """Update the table information display with media (called after delay)"""
        if not self.tables or self.current_index >= len(self.tables):
            self.table_name_label.setText("No Tables Available")
            self.table_info_label.setText("")
            self.table_metadata_label.setText("")
            self.stop_background_video()
            return

        # Update text info first
        self.update_table_info_text_only()

        table = self.tables[self.current_index]

        # Prefer video over image for background
        table_video_path = table.get('table_video', '')
        table_image_path = table.get('image', '')  # playfield image

        if table_video_path:
            self.play_background_video(table_video_path)
        elif table_image_path:
            self.play_background_image(table_image_path)
        else:
            # No media available, stop any current media
            self.stop_background_media()

    def move_wheel_left(self):
        """Move wheel selection to the left with animation (wraps around)"""
        if not self.tables:
            return

        self.current_index = (self.current_index - 1) % len(self.tables)
        self._scroll(-1)

    def move_wheel_right(self):
        """Move wheel selection to the right with animation (wraps around)"""
        if not self.tables:
            return

        self.current_index = (self.current_index + 1) % len(self.tables)
        self._scroll(1)

    def select_current_table(self):
        """Select the currently highlighted table"""
        if self.tables and 0 <= self.current_index < len(self.tables):
            table = self.tables[self.current_index]
            self.table_selected.emit(table)

    def rotate_display(self):
        """Rotate the display 90 degrees clockwise (like PinballX R key)"""
        old_angle = self.rotation_angle
        self.rotation_index = (self.rotation_index + 1) % len(self.rotation_angles)
        self.rotation_angle = self.rotation_angles[self.rotation_index]

        logger.info(f"Rotating display from {old_angle}° to {self.rotation_angle}° (index: {self.rotation_index})")
        print(f"DEBUG: Rotating display from {old_angle}° to {self.rotation_angle}°")

        self._apply_rotation_transform()

        # Emit signal so parent can save to config
        self.rotation_changed.emit(self.rotation_angle)

    def _apply_rotation_transform(self):
        """Apply the current rotation transform to the display"""
        if not hasattr(self, 'background_view'):
            return

        widget_width = self.width()
        widget_height = self.height()

        transform = self._build_rotation_transform(widget_width, widget_height, self.rotation_angle)

        # Apply the transform to the background view
        self.background_view.setTransform(transform)
        logger.debug(f"Applied UI rotation transform: {self.rotation_angle}° (transform applied to background_view)")

        # Apply additional transform to wheel_proxy for 90° and 270° rotations
        if hasattr(self, 'wheel_proxy') and self.rotation_angle == 90:
            wheel_transform = QTransform()
            # Formula for 90°: horizontal = -(width - height * 1.4), vertical = 0
            wheel_transform.translate(-(widget_width - widget_height * 1.4), 0)
            self.wheel_proxy.setTransform(wheel_transform)
        elif hasattr(self, 'wheel_proxy') and self.rotation_angle == 270:
            wheel_transform = QTransform()
            # Formula: horizontal = -(width - height * 1.4), vertical = height * 7/9
            wheel_transform.translate(-(widget_width - widget_height * 1.4), widget_height * 7 / 9)
            self.wheel_proxy.setTransform(wheel_transform)
        elif hasattr(self, 'wheel_proxy'):
            # Reset wheel_proxy transform for other rotations
            self.wheel_proxy.setTransform(QTransform())

        # Apply additional transform to info_proxy for 90° and 270° rotations
        if hasattr(self, 'info_proxy') and self.rotation_angle == 90:
            info_transform = QTransform()
            # Formula for 90°: horizontal = -(width - height * 1.4), vertical = 0
            info_transform.translate(-(widget_width - widget_height * 1.4), 0)
            self.info_proxy.setTransform(info_transform)
        elif hasattr(self, 'info_proxy') and self.rotation_angle == 270:
            info_transform = QTransform()
            # Same formula as wheel_proxy
            info_transform.translate(-(widget_width - widget_height * 1.4), widget_height * 7 / 9)
            self.info_proxy.setTransform(info_transform)
        elif hasattr(self, 'info_proxy'):
            # Reset info_proxy transform for other rotations
            self.info_proxy.setTransform(QTransform())

        # Apply rotation to background video item (90° counter-clockwise from UI rotation)
        self._apply_video_rotation()

        # Apply rotation to background image for 90° and 270° rotations
        self._apply_image_rotation()

        # Update layout to ensure proper positioning
        self._update_scene_layout()

    def _apply_video_rotation(self):
        """Apply rotation to background video for optimal orientation on portrait/landscape screens"""
        if not hasattr(self, 'background_video_item') or not self.background_video_item:
            return

        widget_width = self.width()
        widget_height = self.height()

        # Video should always match the selector rotation
        video_rotation = self.rotation_angle

        # Apply specialized video transform that handles centering correctly
        video_transform = self._build_video_rotation_transform(widget_width, widget_height, video_rotation)

        # For video items, we need to set size and position based on rotation
        if video_rotation in [90, 270]:
            # For 90°/270°, the video content should fill the rotated space
            self.background_video_item.setPos(0, 0)
            self.background_video_item.setSize(QSizeF(widget_width, widget_height))
        else:
            # For 0°/180°, standard sizing
            self.background_video_item.setPos(0, 0)
            self.background_video_item.setSize(QSizeF(widget_width, widget_height))

        self.background_video_item.setTransform(video_transform)

        logger.debug(f"Applied video rotation: {video_rotation}° (Selector: {self.rotation_angle}°, Screen: {widget_width}x{widget_height})")

    def _apply_image_rotation(self):
        """Apply rotation to background image proxy for 90° and 270° rotations only"""
        if not hasattr(self, 'default_background_proxy') or not self.default_background_proxy:
            return

        # Only apply special rotation for 90° and 270° view angles (not 0° or 180°)
        if self.rotation_angle in [90, 270]:
            widget_width = self.width()
            widget_height = self.height()

            # Build the same video transform for consistency
            image_transform = self._build_video_rotation_transform(widget_width, widget_height, self.rotation_angle)
            self.default_background_proxy.setTransform(image_transform)

            logger.debug(f"Applied image rotation transform: {self.rotation_angle}°")
        else:
            # Reset transform for 0° and 180° rotations
            self.default_background_proxy.setTransform(QTransform())
            logger.debug(f"Reset image transform for {self.rotation_angle}° rotation")

    def _build_rotation_transform(self, width: float, height: float, angle: int) -> QTransform:
        """Return a transform that rotates around the center and properly positions the content."""
        transform = QTransform()

        normalized_angle = angle % 360
        if normalized_angle == 0:
            return transform

        # Calculate center point of the widget
        center_x = width / 2.0
        center_y = height / 2.0

        if normalized_angle == 90:
            # For 90° rotation: content rotates clockwise, needs repositioning
            transform.translate(center_x, center_y)
            transform.rotate(90)
            transform.translate(-center_y, -center_x)  # Note: swapped for 90°
        elif normalized_angle == 180:
            # For 180° rotation: simple center rotation
            transform.translate(center_x, center_y)
            transform.rotate(180)
            transform.translate(-center_x, -center_y)
        elif normalized_angle == 270:
            # For 270° rotation: content rotates counter-clockwise, then shift to right edge
            transform.translate(center_x, center_y)
            transform.rotate(270)
            transform.translate(-center_y, -center_x)  # Note: swapped for 270°

        return transform

    def _build_video_rotation_transform(self, width: float, height: float, angle: int) -> QTransform:
        """Return a transform specifically for video rotation that handles centering and orientation properly."""
        transform = QTransform()

        normalized_angle = angle % 360
        if normalized_angle == 0:
            return transform

        # Video elements need different centering logic than UI elements
        center_x = width / 2.0
        center_y = height / 2.0

        if normalized_angle == 90:
            # For 90° rotation: rotate video 90° counter-clockwise (which is -90° or 270°)
            transform.translate(center_x, center_y)
            transform.rotate(270)  # 270° = 90° counter-clockwise
            # Formula: horizontal = (height - width)/2 - height * 9/70 + height/48, vertical = -(height * 8/9)
            transform.translate((height - width) / 2 - height * 9 / 70 + height / 48, -(height * 8 / 9))
        elif normalized_angle == 180:
            # For 180° rotation - standard center rotation
            transform.translate(center_x, center_y)
            transform.rotate(180)
            transform.translate(-center_x, -center_y)
        elif normalized_angle == 270:
            # For 270° rotation: rotate around center, then position at right edge
            # After 270° rotation, translate to align with right edge of screen
            transform.translate(center_x, center_y)
            transform.rotate(270)
            # Formula derived from tested values at different resolutions
            # Vertical offset is always 8/9 of height
            # Horizontal offset is (width - height/2)
            transform.translate(-(width - height / 2), -(height * 8 / 9))
        return transform

    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        self._update_scene_layout()

        # Reapply rotation transform with new dimensions if we're currently rotated
        if self.rotation_angle != 0:
            QTimer.singleShot(50, lambda: self._reapply_rotation())

        QTimer.singleShot(50, lambda: self.update_wheel_display(animate=False))

    def _reapply_rotation(self):
        """Reapply the current rotation with updated widget dimensions"""
        if self.rotation_angle != 0:
            # Just reapply the transform with current dimensions
            self._apply_rotation_transform()

    def _update_scene_layout(self):
        """Resize graphics scene items to match the widget."""
        if not hasattr(self, 'background_view'):
            return

        width = max(0, self.width())
        height = max(0, self.height())

        self.background_view.setGeometry(0, 0, width, height)
        self.background_scene.setSceneRect(QRectF(0, 0, width, height))

        if hasattr(self, 'background_video_item'):
            # Video positioning and sizing is handled by _apply_video_rotation
            # Always apply video rotation since video should always be oriented correctly
            if hasattr(self, 'rotation_angle'):
                self._apply_video_rotation()
            else:
                # Only set default position/size if no rotation angle is set
                self.background_video_item.setPos(0, 0)
                self.background_video_item.setSize(QSizeF(width, height))

        if hasattr(self, 'default_background_proxy'):
            self.default_background_proxy.setGeometry(QRectF(0, 0, width, height))
            self.default_background.resize(int(width), int(height))

        info_height = self.INFO_HEIGHT
        # Logical width that is actually on screen (the scene is wider when rotated 90/270)
        visible_width = height if getattr(self, 'rotation_angle', 0) in (90, 270) else width

        # Info panel placement: centred under the wheel, near the bottom edge
        if hasattr(self, 'info_proxy'):
            info_width = max(0, min(980, int(visible_width * 0.6), width - 40))
            info_x = (width - info_width) / 2
            info_top_y = max(0, height - info_height - 28)
            self.info_proxy.setGeometry(QRectF(info_x, info_top_y, info_width, info_height))
            self.info_widget.resize(int(info_width), info_height)

        # Wheel container spans to the bottom of the screen; the stage sits behind the info panel
        if hasattr(self, 'wheel_proxy'):
            wheel_y = 20.0
            wheel_height = max(0.0, height - wheel_y)
            self.wheel_proxy.setGeometry(QRectF(0, wheel_y, width, wheel_height))
            self.wheel_container.resize(int(width), int(wheel_height))
            if hasattr(self, 'wheel_canvas'):
                self.wheel_canvas.setGeometry(0, 0, int(width), int(wheel_height))
                self.wheel_canvas.set_layout_metrics(int(visible_width), info_height + 40)

    def keyPressEvent(self, event):
        """Handle key press events"""
        key = event.key()

        if key == Qt.Key.Key_Left:
            self.move_wheel_left()
        elif key == Qt.Key.Key_Right:
            self.move_wheel_right()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.select_current_table()
        elif key == Qt.Key.Key_R:
            self.rotate_display()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle widget close event"""
        logger.debug("WheelWidget closeEvent started")

        try:
            # Stop all timers to prevent hanging
            if hasattr(self, 'media_update_timer') and self.media_update_timer:
                self.media_update_timer.stop()
                logger.debug("Stopped media_update_timer")


            # Stop loading popup timers if they exist
            # The loading popup might not exist as it's created dynamically
            for child in self.findChildren(LoadingPopup):
                if hasattr(child, 'spinner_timer'):
                    child.spinner_timer.stop()
                if hasattr(child, 'fade_timer'):
                    child.fade_timer.stop()
                if hasattr(child, 'fade_out_timer'):
                    child.fade_out_timer.stop()
            logger.debug("Stopped loading popup timers")

            # Stop wheel motion
            if hasattr(self, 'wheel_canvas') and self.wheel_canvas:
                self.wheel_canvas.jump_to(self.current_index)

            # Stop background video and clean up media player - DO THIS SYNCHRONOUSLY
            if hasattr(self, 'background_media_player') and self.background_media_player:
                logger.debug("Stopping background media player...")
                try:
                    # Stop playback first
                    self.background_media_player.stop()
                    # Wait a bit for stop to complete
                    QApplication.processEvents()
                    # Clear source
                    self.background_media_player.setSource(QUrl())
                    # Disconnect outputs
                    self.background_media_player.setVideoOutput(None)
                    self.background_media_player.setAudioOutput(None)
                    logger.debug("Background media player stopped and cleared")
                except Exception as e:
                    logger.error(f"Error stopping background media player: {e}")

            # Clean up audio output
            if hasattr(self, 'background_audio_output'):
                self.background_audio_output = None
                logger.debug("Cleaned up audio output")

            logger.debug("WheelWidget closeEvent completed successfully")

        except Exception as e:
            logger.error(f"Error in WheelWidget closeEvent: {e}", exc_info=True)

        super().closeEvent(event)


class WheelMainWindow(QWidget):
    """Main window with PinballX-style wheel interface"""

    # Signals
    table_selected = pyqtSignal(str)  # table file path
    exit_requested = pyqtSignal()

    def __init__(self, config, monitor_manager, table_service=None, launch_manager=None):
        super().__init__()
        self.config = config
        self.monitor_manager = monitor_manager
        self.table_service = table_service
        self.launch_manager = launch_manager
        self.logger = get_logger(__name__)

        # Initialize audio players
        self.audio_player = AudioPlayer(self)  # For launch sounds
        self.nav_audio_player = AudioPlayer(self)  # For navigation sounds
        self.nav_audio_player.set_volume(0.3)  # Lower volume for UI sounds
        self.table_audio_player = AudioPlayer(self)  # For table-specific audio
        self.table_audio_player.set_volume(0.5)  # Medium volume for table audio

        # Load navigation sound if available
        self.nav_sound_path = self._find_navigation_sound()

        # Initialize input manager
        self.input_manager = InputManager(config=self.config, parent=self)
        self.input_manager.action_triggered.connect(self.handle_input_action)

        # Connect to launch manager signals
        if self.launch_manager:
            self.launch_manager.launcher.table_launched.connect(self._on_table_launched)
            self.launch_manager.launcher.table_exited.connect(self._on_table_exited)
            # Without these, a crashed table or failed launch leaves the loading popup up
            # and joystick polling stopped
            self.launch_manager.launcher.table_crashed.connect(self._on_table_crashed_or_failed)
            self.launch_manager.launcher.launch_failed.connect(self._on_table_crashed_or_failed)

        self.setup_ui()
        self.load_tables()

        # Loading popup (created after setup_ui so it has a parent geometry)
        self.loading_popup = LoadingPopup(self)

        # Set focus policy to receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Start input polling
        self.input_manager.start_polling()

    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("PinballUX - Wheel Interface")
        self.setStyleSheet("background-color: #1a1a1a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Wheel widget
        self.wheel_widget = WheelWidget()
        self.wheel_widget.table_selected.connect(self.on_table_selected)
        self.wheel_widget.table_highlighted.connect(self.on_table_highlighted)
        self.wheel_widget.table_navigation.connect(self.on_table_navigation)
        self.wheel_widget.rotation_changed.connect(self.on_rotation_changed)

        # Set rotation from config if available
        if self.config and self.config.displays.playfield:
            target_rotation = self.config.displays.playfield.rotation
            self.logger.info(f"Applying playfield rotation from config: {target_rotation}°")
            # Find the index for the target rotation
            if target_rotation in self.wheel_widget.rotation_angles:
                self.wheel_widget.rotation_index = self.wheel_widget.rotation_angles.index(target_rotation)
                self.wheel_widget.rotation_angle = target_rotation
                # Apply the rotation
                self.wheel_widget._apply_rotation_transform()
                self.logger.info(f"Playfield rotation set to {target_rotation}°")
            else:
                self.logger.warning(f"Invalid rotation angle in config: {target_rotation}, valid values are {self.wheel_widget.rotation_angles}")

        layout.addWidget(self.wheel_widget)

        # Set focus to wheel widget so it can receive key events
        self.wheel_widget.setFocus()

    def showEvent(self, event):
        """Handle window show event"""
        super().showEvent(event)
        # Ensure wheel widget has focus when window is shown
        self.wheel_widget.setFocus()
        # Also ensure this window has focus
        self.setFocus()
        self.activateWindow()
        self.raise_()


    def load_tables(self):
        """Load tables from database"""
        if not self.table_service:
            self.logger.warning("No table service available")
            return

        try:
            tables = self.table_service.get_all_tables()
            self.logger.info(f"Loaded {len(tables)} tables for wheel")

            # Convert Table models to dict format - use database as source of truth
            table_data = []
            for table in tables:
                # Use database fields directly - database is the source of truth
                # Fallback to playfield_image for wheel if no dedicated wheel image
                wheel_image_path = table.wheel_image or table.playfield_image or ''

                data = {
                    'id': table.id,
                    'name': table.name,
                    'manufacturer': table.manufacturer or '',
                    'year': table.year or '',
                    'file_path': table.file_path,
                    'wheel_image': wheel_image_path,
                    'image': table.playfield_image or '',  # playfield image for background
                    'table_video': table.table_video or '',
                    'backglass_image': table.backglass_image or '',
                    'backglass_video': table.backglass_video or '',
                    'dmd_image': table.dmd_image or '',
                    'dmd_video': table.dmd_video or '',
                    'topper_image': table.topper_image or '',
                    'topper_video': table.topper_video or '',
                    'table_audio': table.table_audio or '',
                    'launch_audio': table.launch_audio or '',
                    'play_count': table.play_count or 0,
                    'rating': table.rating or 0,
                    'description': table.description or '',
                    'theme': table.theme or '',
                    'ipdb_number': table.ipdb_number or 0,
                    'players': table.players or 1,
                    'author': table.author or ''
                }

                table_data.append(data)

            self.wheel_widget.set_tables(table_data)

        except Exception as e:
            self.logger.error(f"Failed to load tables: {e}")

    def on_table_selected(self, table_data: dict):
        """Handle table selection from wheel"""
        table_name = table_data.get('name', 'Unknown')
        table_id = table_data.get('id')

        self.logger.info(f"Table selected: {table_name}")

        # Stop table audio when launching
        if self.table_audio_player.is_playing():
            self.table_audio_player.stop()
            self.logger.debug("Stopped table audio for launch")

        # Play launch audio if available
        launch_audio = table_data.get('launch_audio', '')
        if launch_audio:
            self.audio_player.play_once(launch_audio)
            self.logger.info(f"Playing launch audio: {launch_audio}")

        # Update displays - DON'T update backglass, just show loading screen
        if self.monitor_manager:
            # Update DMD with launching message
            dmd_video = table_data.get('dmd_video', '')
            dmd_image = table_data.get('dmd_image', '')
            if dmd_video or dmd_image:
                self.monitor_manager.update_display_content("dmd", {
                    'dmd_video': dmd_video,
                    'dmd_image': dmd_image,
                    'animation': False
                })
            else:
                self.monitor_manager.update_display_content("dmd", {
                    'message': f"LAUNCHING: {table_name[:12].upper()}",
                    'animation': True
                })

            # Show loading screen on backglass (replaces any content)
            self.logger.info(f"Requesting loading screen on backglass for '{table_name}'")
            self.monitor_manager.show_loading("backglass", table_name)
        else:
            self.logger.warning("No monitor_manager available for loading screen")

        # Launch table
        if self.launch_manager and table_id:
            success = self.launch_manager.launch_table_by_id(table_id)
            if not success:
                self.logger.error("Failed to launch table")
                if self.monitor_manager:
                    self.monitor_manager.update_display_content("dmd", {
                        'message': "LAUNCH FAILED",
                        'animation': False
                    })

    def _find_navigation_sound(self) -> str:
        """Find navigation sound file"""
        if not self.config or not self.config.vpx.media_directory:
            return ''

        # Look for flipper/click sound in UI audio directory
        ui_audio_dir = Path(self.config.vpx.media_directory) / "audio" / "ui"

        if ui_audio_dir.exists():
            # Try different possible names
            sound_names = ['flipper', 'click', 'nav', 'navigation', 'wheel']
            audio_extensions = ['.mp3', '.wav', '.ogg']

            for name in sound_names:
                for ext in audio_extensions:
                    sound_file = ui_audio_dir / f"{name}{ext}"
                    if sound_file.exists():
                        self.logger.info(f"Found navigation sound: {sound_file}")
                        return str(sound_file)

        return ''

    def _play_navigation_sound(self):
        """Play navigation sound when changing tables"""
        if self.nav_sound_path and self.nav_audio_player:
            self.nav_audio_player.play_once(self.nav_sound_path)

    def on_table_navigation(self):
        """Handle immediate navigation feedback when wheel moves

        This is called immediately when user presses navigation buttons.
        Only plays sound and stops table audio - no heavy media loading.
        """
        self.logger.debug("Quick navigation - playing flipper sound, stopping table audio")

        # Play navigation sound immediately
        self._play_navigation_sound()

        # Stop table audio immediately when navigating
        if self.table_audio_player.is_playing():
            self.table_audio_player.stop()
            self.logger.debug("Stopped table audio during navigation")

    def on_table_highlighted(self, table_data: dict):
        """Handle table highlight after wheel stops moving

        This is only called after the delay when wheel stops.
        Loads all heavy media (backglass, DMD, table audio, etc.)
        """
        table_name = table_data.get('name', 'Unknown')
        self.logger.debug(f"Wheel stopped on {table_name} - loading all media")

        # Play table audio if enabled and available
        if self.config.audio.table_audio:
            table_audio = table_data.get('table_audio', '')
            if table_audio:
                self.table_audio_player.play_once(table_audio)
                self.logger.debug(f"Playing table audio: {table_audio}")

        # Update displays with highlighted table info
        if self.monitor_manager:
            self.monitor_manager.update_display_content("backglass", {
                'table_name': table_name,
                'manufacturer': table_data.get('manufacturer', ''),
                'year': table_data.get('year', ''),
                'backglass_video': table_data.get('backglass_video', ''),
                'backglass_image': table_data.get('backglass_image', '')
            })

            # Update DMD with video/image if available, otherwise show message
            dmd_video = table_data.get('dmd_video', '')
            dmd_image = table_data.get('dmd_image', '')
            if dmd_video or dmd_image:
                self.monitor_manager.update_display_content("dmd", {
                    'dmd_video': dmd_video,
                    'dmd_image': dmd_image,
                    'animation': False
                })
            else:
                self.monitor_manager.update_display_content("dmd", {
                    'message': f"SELECTED: {table_name[:12].upper()}",
                    'animation': False
                })

    def _on_table_launched(self, table_path: str):
        """Handle table launched - show loading popup and blank other displays"""
        self.logger.info(f"Table launched, showing loading popup")

        # Stop input polling to avoid interfering with VPX input
        if self.input_manager:
            self.input_manager.stop_polling()
            self.logger.info("Stopped input polling - VPX will handle all input")

        # Show loading popup over the wheel
        table_name = Path(table_path).stem
        rotation = self.config.displays.playfield.rotation if self.config and self.config.displays.playfield else 0
        self.loading_popup.show_loading(table_name, rotation_angle=rotation)

        if self.monitor_manager:
            self.monitor_manager.hide_loading("backglass")

        # Let launch audio play for 3 seconds before stopping it
        # This allows the user to hear the launch sound before VPX audio takes over
        if self.audio_player.is_playing():
            QTimer.singleShot(3000, lambda: self._stop_launch_audio_if_playing())
            self.logger.debug("Will stop launch audio in 3 seconds")

        if self.monitor_manager:
            # Blank DMD screen - just black, no text
            self.monitor_manager.update_display_content("dmd", {
                'message': '',
                'animation': False
            })

            # Optional: Also clear backglass if you want
            # self.monitor_manager.update_display_content("backglass", {
            #     'table_name': '',
            #     'manufacturer': '',
            #     'year': '',
            #     'backglass_image': '',
            #     'backglass_video': ''
            # })

    def _stop_launch_audio_if_playing(self):
        """Stop launch audio if still playing (called after delay)"""
        if self.audio_player.is_playing():
            self.audio_player.stop()
            self.logger.debug("Stopped launch audio after delay")

    def _on_table_exited(self, table_path: str, exit_code: int, duration: int):
        """Handle table exit - restore displays"""
        self.logger.info(f"Table exited, restoring displays")
        self.loading_popup.hide_loading()


        # Restart input polling for frontend navigation
        if self.input_manager:
            self.input_manager.start_polling()
            self.logger.info("Restarted input polling - PinballUX controls active")

        # Restore the current table's display content
        if self.wheel_widget and self.wheel_widget.tables and 0 <= self.wheel_widget.current_index < len(self.wheel_widget.tables):
            current_table = self.wheel_widget.tables[self.wheel_widget.current_index]
            self.on_table_highlighted(current_table)

    def _on_table_crashed_or_failed(self, table_path: str, error_message: str):
        """Handle a crashed table or failed launch - return to the wheel like a normal exit"""
        self.logger.warning(f"Table ended abnormally ({error_message}), restoring frontend")
        self._on_table_exited(table_path, -1, 0)

    def on_rotation_changed(self, rotation_angle: int):
        """Handle rotation change - save to config"""
        self.logger.info(f"Rotation changed to {rotation_angle}°, saving to config")

        if self.config and self.config.displays.playfield:
            self.config.displays.playfield.rotation = rotation_angle
            self.config.save()
            self.logger.info(f"Saved playfield rotation to config: {rotation_angle}°")
        else:
            self.logger.warning("Cannot save rotation: config or playfield config not available")

    def handle_input_action(self, action: InputAction):
        """Handle input actions from keyboard or joystick"""
        self.logger.debug(f"Received input action: {action}")

        if action == InputAction.WHEEL_LEFT:
            self.logger.debug("Moving wheel left")
            self.wheel_widget.move_wheel_left()
        elif action == InputAction.WHEEL_RIGHT:
            self.logger.debug("Moving wheel right")
            self.wheel_widget.move_wheel_right()
        elif action == InputAction.SELECT:
            self.logger.debug("Selecting current table")
            self.wheel_widget.select_current_table()
        elif action == InputAction.EXIT:
            self.logger.debug("Exit requested")
            self.exit_requested.emit()
        elif action == InputAction.ROTATE:
            self.logger.debug("Rotating display")
            self.wheel_widget.rotate_display()
        elif action == InputAction.MENU:
            # Could open a menu in the future
            pass
        # Add more action handlers as needed

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Forward key events to input manager only - don't call super() to avoid double handling
        self.logger.debug(f"WheelMainWindow keyPressEvent: {event.key()}, scan: {event.nativeScanCode()}")
        self.input_manager.handle_key_press(event.key(), event.nativeScanCode())
        # Don't call super() to prevent double handling in WheelWidget.keyPressEvent()

    def closeEvent(self, event):
        """Handle close event"""
        logger.debug("WheelMainWindow closeEvent started")

        try:
            # Stop input polling first to prevent any new events
            if hasattr(self, 'input_manager') and self.input_manager:
                logger.debug("Stopping input manager...")
                self.input_manager.stop_polling()
                logger.debug("Input polling stopped")

            # Clean up audio players - stop them synchronously
            if hasattr(self, 'audio_player') and self.audio_player:
                logger.debug("Stopping audio player...")
                self.audio_player.stop()
                QApplication.processEvents()
                logger.debug("Audio player stopped")

            if hasattr(self, 'nav_audio_player') and self.nav_audio_player:
                logger.debug("Stopping nav audio player...")
                self.nav_audio_player.stop()
                QApplication.processEvents()
                logger.debug("Nav audio player stopped")

            if hasattr(self, 'table_audio_player') and self.table_audio_player:
                logger.debug("Stopping table audio player...")
                self.table_audio_player.stop()
                QApplication.processEvents()
                logger.debug("Table audio player stopped")

            # Clean up wheel widget media players
            if hasattr(self, 'wheel_widget') and self.wheel_widget:
                logger.debug("Cleaning up wheel widget...")
                try:
                    # Stop background video first
                    self.wheel_widget.stop_background_video()
                    QApplication.processEvents()

                    # Clean up background media player
                    if hasattr(self.wheel_widget, 'background_media_player') and self.wheel_widget.background_media_player:
                        logger.debug("Stopping wheel background media player...")
                        self.wheel_widget.background_media_player.stop()
                        QApplication.processEvents()
                        self.wheel_widget.background_media_player.setSource(QUrl())
                        self.wheel_widget.background_media_player.setVideoOutput(None)
                        self.wheel_widget.background_media_player.setAudioOutput(None)
                        logger.debug("Wheel background media player stopped")

                    if hasattr(self.wheel_widget, 'background_audio_output'):
                        self.wheel_widget.background_audio_output = None

                    if hasattr(self.wheel_widget, 'background_video_item') and self.wheel_widget.background_video_item:
                        self.wheel_widget.background_video_item.setParent(None)
                        self.wheel_widget.background_video_item = None

                    logger.debug("Wheel widget cleaned up")

                except Exception as e:
                    logger.error(f"Error cleaning up wheel widget: {e}", exc_info=True)

            # Clean up input manager last
            if hasattr(self, 'input_manager') and self.input_manager:
                logger.debug("Final input manager cleanup...")
                self.input_manager.cleanup()
                logger.debug("Input manager cleaned up")

            logger.debug("WheelMainWindow closeEvent completed successfully")

        except Exception as e:
            logger.error(f"Error in WheelMainWindow closeEvent: {e}", exc_info=True)

        super().closeEvent(event)
