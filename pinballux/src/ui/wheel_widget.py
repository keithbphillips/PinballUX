"""
PinballX-style wheel widget for table selection
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsView, QGraphicsScene, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QSizeF, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QRect, pyqtProperty, QUrl
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QBrush, QLinearGradient, QPen, QPainterPath, QTransform
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem

from typing import List
from pathlib import Path

from ..core.logger import get_logger
from ..input.input_manager import InputManager, InputAction
from .media_widgets import AudioPlayer

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


class WheelBackground(QWidget):
    """Futuristic semi-circular background widget with glowing neon effects"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Animation timer for pulsing glow effect
        self.glow_intensity = 0.0
        self.glow_direction = 1
        self.glow_timer = QTimer()
        self.glow_timer.timeout.connect(self._update_glow)
        self.glow_timer.start(50)  # Update every 50ms for smooth animation

    def _update_glow(self):
        """Update glow animation"""
        self.glow_intensity += 0.02 * self.glow_direction
        if self.glow_intensity >= 1.0:
            self.glow_intensity = 1.0
            self.glow_direction = -1
        elif self.glow_intensity <= 0.0:
            self.glow_intensity = 0.0
            self.glow_direction = 1
        self.update()

    def paintEvent(self, event):
        """Draw a futuristic wheel background with glowing neon effects - unified curved stage"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width // 2

        # Create a stage with flat bottom and curved top
        arc_width = width * 0.95  # Wide but within bounds

        # Bottom line extends to bottom of screen
        bottom_y = height

        # Arc positioned very close to bottom - within 150px of bottom edge
        arc_center_y = height - 150 if height > 300 else height * 0.85
        arc_height = 100  # Fixed small arc height for consistent curve

        # Create unified curved path
        wheel_path = QPainterPath()

        # Start at left bottom corner
        left_x = center_x - arc_width / 2
        right_x = center_x + arc_width / 2

        # Draw the shape: left vertical line up to just below arc, arc across top, right vertical down, bottom line
        wheel_path.moveTo(left_x, bottom_y)

        # Left vertical line up to just below the arc
        wheel_path.lineTo(left_x, arc_center_y)

        # Arc across the top - smaller ellipse for gentler curve
        arc_top = arc_center_y - arc_height
        arc_rect = QRectF(left_x, arc_top, arc_width, arc_height * 2)
        wheel_path.arcTo(arc_rect, 180, -180)  # From left (180°) sweep -180° clockwise to right (0°)

        # Right vertical line down to bottom
        wheel_path.lineTo(right_x, bottom_y)

        # Bottom horizontal line back to start
        wheel_path.lineTo(left_x, bottom_y)

        wheel_path.closeSubpath()

        # Background gradient - dark with subtle blue tint, extends to bottom
        arc_top = arc_center_y - arc_height
        bg_gradient = QLinearGradient(center_x, arc_top, center_x, bottom_y)
        bg_gradient.setColorAt(0, QColor(15, 20, 35, 250))  # Dark blue-tinted top
        bg_gradient.setColorAt(0.3, QColor(10, 15, 25, 250))  # Darker middle
        bg_gradient.setColorAt(1, QColor(20, 25, 40, 250))  # Slightly lighter bottom
        painter.fillPath(wheel_path, QBrush(bg_gradient))

        # Draw multiple glowing neon borders for futuristic effect
        glow_alpha = int(150 + 50 * self.glow_intensity)  # Pulsing glow

        # Outer glow (widest, most transparent)
        for i in range(3):
            glow_width = 8 - i * 2
            glow_alpha_layer = glow_alpha // (i + 2)

            glow_gradient = QLinearGradient(0, arc_center_y, width, arc_center_y)
            glow_gradient.setColorAt(0, QColor(0, 150, 255, glow_alpha_layer))  # Cyan
            glow_gradient.setColorAt(0.5, QColor(100, 180, 255, glow_alpha_layer))  # Bright cyan
            glow_gradient.setColorAt(1, QColor(180, 100, 255, glow_alpha_layer))  # Purple

            glow_pen = QPen(QBrush(glow_gradient), glow_width)
            painter.setPen(glow_pen)
            painter.drawPath(wheel_path)

        # Inner accent line (sharp, bright)
        accent_gradient = QLinearGradient(0, arc_center_y, width, arc_center_y)
        accent_gradient.setColorAt(0, QColor(0, 200, 255, 200))
        accent_gradient.setColorAt(0.5, QColor(150, 220, 255, 255))
        accent_gradient.setColorAt(1, QColor(200, 150, 255, 200))

        accent_pen = QPen(QBrush(accent_gradient), 1)
        painter.setPen(accent_pen)
        painter.drawPath(wheel_path)

        # Add inner arc for depth - slightly smaller
        inner_width = arc_width * 0.90
        inner_height = arc_height * 0.85
        inner_arc_top = arc_center_y - inner_height
        inner_arc_rect = QRectF(center_x - inner_width / 2, inner_arc_top,
                               inner_width, inner_height * 2)

        inner_path = QPainterPath()
        inner_path.arcMoveTo(inner_arc_rect, 180)
        inner_path.arcTo(inner_arc_rect, 180, -180)

        # Subtle inner glow
        inner_glow_gradient = QLinearGradient(center_x, inner_arc_top, center_x, arc_center_y)
        inner_glow_gradient.setColorAt(0, QColor(50, 100, 150, 80))
        inner_glow_gradient.setColorAt(1, QColor(50, 100, 150, 30))

        inner_pen = QPen(QBrush(inner_glow_gradient), 2)
        painter.setPen(inner_pen)
        painter.drawPath(inner_path)

        painter.end()

class WheelItem(QLabel):
    """Individual wheel item displaying a table's wheel image with glow effects"""

    def __init__(self, table_data: dict, parent=None):
        super().__init__(parent)
        self.table_data = table_data
        self.is_selected = False
        self.is_center = False
        self._scale_factor = 1.0
        self._animated_scale = 1.0

        self.setFixedSize(200, 200)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)

        # Load wheel image
        self.load_wheel_image()

        # Glow animation for selected item
        self.glow_intensity = 0.0
        self.glow_timer = None

    @pyqtProperty(float)
    def animated_scale(self):
        """Property for animating scale factor"""
        return self._animated_scale

    @animated_scale.setter
    def animated_scale(self, value):
        """Set animated scale and update display"""
        self._animated_scale = value
        self.update_scaled_pixmap()

    def load_wheel_image(self):
        """Load the wheel image for this table"""
        wheel_image_path = self.table_data.get('wheel_image', '')

        if wheel_image_path and Path(wheel_image_path).exists():
            try:
                pixmap = QPixmap(wheel_image_path)
                if not pixmap.isNull():
                    self.original_pixmap = pixmap
                    self.update_scaled_pixmap()
                    return
            except Exception as e:
                logger.warning(f"Failed to load wheel image {wheel_image_path}: {e}")

        # Create default wheel image with table name
        self.create_default_wheel_image()

    def create_default_wheel_image(self):
        """Create a default wheel image with table name text"""
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor(50, 50, 50))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw border
        painter.setPen(QColor(100, 100, 100))
        painter.drawRoundedRect(5, 5, 190, 190, 10, 10)

        # Draw table name
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 12, QFont.Weight.Bold)
        painter.setFont(font)

        table_name = self.table_data.get('name', 'Unknown Table')
        # Wrap text if too long
        if len(table_name) > 20:
            words = table_name.split()
            line1 = ' '.join(words[:len(words)//2])
            line2 = ' '.join(words[len(words)//2:])

            painter.drawText(10, 90, 180, 30, int(Qt.AlignmentFlag.AlignCenter), line1)
            painter.drawText(10, 110, 180, 30, int(Qt.AlignmentFlag.AlignCenter), line2)
        else:
            painter.drawText(10, 85, 180, 30, int(Qt.AlignmentFlag.AlignCenter), table_name)

        # Draw manufacturer and year
        manufacturer = self.table_data.get('manufacturer', '')
        year = self.table_data.get('year', '')
        info_text = f"{manufacturer} ({year})" if manufacturer and year else str(manufacturer or year or '')

        if info_text:
            font = QFont("Arial", 10)
            painter.setFont(font)
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(10, 130, 180, 20, int(Qt.AlignmentFlag.AlignCenter), info_text)

        painter.end()

        self.original_pixmap = pixmap
        self.update_scaled_pixmap()

    def update_scaled_pixmap(self):
        """Update the displayed pixmap with current scale factor"""
        if hasattr(self, 'original_pixmap'):
            # Use animated scale if available, otherwise fall back to scale_factor
            current_scale = self._animated_scale if hasattr(self, '_animated_scale') else self._scale_factor
            size = int(200 * current_scale)
            scaled_pixmap = self.original_pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)

    def set_scale_factor(self, scale: float):
        """Set the target scale factor for this wheel item"""
        self._scale_factor = scale
        self._animated_scale = scale  # Set animated scale to match
        self.update_scaled_pixmap()

    @property
    def scale_factor(self):
        """Get current scale factor"""
        return self._scale_factor

    def set_selected(self, selected: bool):
        """Set the selection state - no borders for circular theme"""
        self.is_selected = selected

        if selected:
            # No border - clean circular theme
            # Just transparent background
            self.setStyleSheet("""
                border: none;
                border-radius: 0px;
                background-color: transparent;
            """)

            # Stop glow animation if running (we're not using it anymore)
            if self.glow_timer:
                self.glow_timer.stop()
                self.glow_timer = None
        else:
            # No border for non-selected items either
            self.setStyleSheet("""
                border: none;
                border-radius: 0px;
                background-color: transparent;
            """)

    def _update_glow(self):
        """Update glow animation - currently disabled for clean circular theme"""
        pass


class WheelWidget(QWidget):
    """PinballX-style wheel widget for table selection"""

    # Signals
    table_selected = pyqtSignal(dict)  # table_data
    table_highlighted = pyqtSignal(dict)  # table_data
    rotation_changed = pyqtSignal(int)  # rotation_angle

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)

        # Wheel state
        self.tables = []
        self.wheel_items = []
        self.current_index = 0
        self.visible_items = 7  # Number of items visible on wheel

        # Animation system
        self.animation_group = None
        self.animation_duration = 350  # ms - smooth but not too slow
        self.is_animating = False

        # Delayed media update system
        self.media_update_timer = QTimer()
        self.media_update_timer.setSingleShot(True)
        self.media_update_timer.timeout.connect(self._delayed_media_update)
        self.media_update_delay = 100  # ms delay after animation stops

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

        # Add wheel background
        self.wheel_background = WheelBackground(self.wheel_container)
        self.wheel_background.lower()  # Ensure it's behind wheel items

        self.wheel_proxy = self.background_scene.addWidget(self.wheel_container)
        self.wheel_proxy.setZValue(10)

        # Table info display embedded in the scene
        self.info_widget = QWidget()
        self.info_widget.setFixedHeight(120)
        self.info_widget.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 15px;
            border: 2px solid rgba(255, 255, 255, 0.3);
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
        layout.setContentsMargins(20, 10, 20, 10)

        # Table name
        self.table_name_label = QLabel("Select a Table")
        self.table_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_name_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(self.table_name_label)

        # Table info (manufacturer, year, play count)
        self.table_info_label = QLabel("")
        self.table_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_info_label.setStyleSheet("font-size: 16px; color: #ccc;")
        layout.addWidget(self.table_info_label)

        # Table metadata (theme, IPDB, players, author)
        self.table_metadata_label = QLabel("")
        self.table_metadata_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_metadata_label.setStyleSheet("font-size: 14px; color: #aaa;")
        self.table_metadata_label.setWordWrap(True)
        layout.addWidget(self.table_metadata_label)

    def set_tables(self, tables: List[dict]):
        """Set the tables for the wheel"""
        self.tables = tables
        self.current_index = 0

        # Clear existing wheel items
        for item in self.wheel_items:
            item.setParent(None)
        self.wheel_items.clear()

        # Create wheel items
        for table in tables:
            wheel_item = WheelItem(table)
            wheel_item.setParent(self.wheel_container)
            self.wheel_items.append(wheel_item)

        self.update_wheel_display(animate=False)  # No animation on initial setup

    def update_wheel_display(self, animate=True):
        """Update the wheel display positions and scaling with optional animation"""
        if not self.wheel_items:
            return

        container_width = self.wheel_container.width()
        container_height = self.wheel_container.height()
        if container_width <= 0 or container_height <= 0:
            # If container has no size, force immediate update without animation
            animate = False

        if animate:
            self._animate_wheel_display()
        else:
            self._update_wheel_display_immediate()

    def _update_wheel_display_immediate(self):
        """Update wheel display immediately without animation"""
        # Cancel any pending delayed media update since we're updating immediately
        if hasattr(self, 'media_update_timer') and self.media_update_timer.isActive():
            self.media_update_timer.stop()

        container_width = self.wheel_container.width()
        container_height = self.wheel_container.height()
        center_x = container_width // 2
        # Position items very close to bottom, matching arc position (within 150px of bottom)
        center_y = int(container_height - 150) if container_height > 300 else int(container_height * 0.85)

        # Calculate positions for visible items
        start_index = max(0, self.current_index - self.visible_items // 2)
        end_index = min(len(self.wheel_items), start_index + self.visible_items)

        # Hide all items first
        for item in self.wheel_items:
            item.hide()

        # Position visible items
        for i in range(start_index, end_index):
            item = self.wheel_items[i]
            relative_pos = i - self.current_index

            # Calculate horizontal position (wheel effect)
            x_offset = relative_pos * 220  # Spacing between items

            # Improved 3D perspective curve - parabolic y-offset for better depth
            # Items arc upward as they move away from center
            y_offset = (relative_pos ** 2) * 8  # Quadratic curve for 3D depth effect

            # Scale factor based on distance from center with smoother falloff
            if relative_pos == 0:
                scale_factor = 1.0  # Center item
                item.set_selected(True)
            else:
                # Smooth exponential falloff for scale
                distance = abs(relative_pos)
                scale_factor = max(0.55, 1.0 - distance * 0.18)
                item.set_selected(False)

            item.set_scale_factor(scale_factor)

            # Position the item
            item_width = int(200 * scale_factor)
            item_height = int(200 * scale_factor)
            x = center_x + x_offset - item_width // 2
            y = center_y + y_offset - item_height // 2

            item.setGeometry(x, y, item_width, item_height)
            item.show()

        # Update table info
        self.update_table_info()

    def _animate_wheel_display(self):
        """Animate the wheel display with smooth transitions"""
        container_width = self.wheel_container.width()
        container_height = self.wheel_container.height()

        # If container has no proper size, fall back to immediate update
        if container_width <= 0 or container_height <= 0:
            logger.debug("Container has no size, falling back to immediate update")
            self._update_wheel_display_immediate()
            return

        # Stop any existing animation first (allows rapid movement)
        if self.animation_group and self.animation_group.state() != QParallelAnimationGroup.State.Stopped:
            self.animation_group.stop()
            try:
                self.animation_group.finished.disconnect()
            except:
                pass  # Signal might not be connected

        # Cancel any pending media update from previous animation
        if self.media_update_timer.isActive():
            self.media_update_timer.stop()
            self.logger.debug("Cancelled pending media update due to new wheel movement")

        self.is_animating = True
        center_x = container_width // 2
        # Position items very close to bottom, matching arc position (within 150px of bottom)
        center_y = int(container_height - 150) if container_height > 300 else int(container_height * 0.85)

        self.animation_group = QParallelAnimationGroup()

        # Calculate positions for visible items
        start_index = max(0, self.current_index - self.visible_items // 2)
        end_index = min(len(self.wheel_items), start_index + self.visible_items)

        # If no items to animate, fall back to immediate update
        if start_index >= end_index:
            self.is_animating = False
            logger.debug("No items in range, falling back to immediate update")
            self._update_wheel_display_immediate()
            return

        # First, position and prepare items before showing them to avoid flash
        for i in range(len(self.wheel_items)):
            if start_index <= i < end_index:
                item = self.wheel_items[i]
                relative_pos = i - self.current_index

                # Calculate target position for this item
                x_offset = relative_pos * 220
                y_offset = (relative_pos ** 2) * 8

                if relative_pos == 0:
                    target_scale = 1.0
                else:
                    distance = abs(relative_pos)
                    target_scale = max(0.55, 1.0 - distance * 0.18)

                target_width = int(200 * target_scale)
                target_height = int(200 * target_scale)
                target_x = center_x + x_offset - target_width // 2
                target_y = center_y + y_offset - target_height // 2

                # If item was hidden, position it at target location BEFORE showing
                # This prevents the flash of the old position
                if not item.isVisible():
                    item.setGeometry(target_x, target_y, target_width, target_height)
                    item._animated_scale = target_scale

                # Now show the item (it's already positioned correctly)
                item.show()
            else:
                self.wheel_items[i].hide()

        # Animate visible items
        for i in range(start_index, end_index):
            item = self.wheel_items[i]
            relative_pos = i - self.current_index

            # Calculate target position (wheel effect)
            x_offset = relative_pos * 220  # Spacing between items

            # Improved 3D perspective curve - parabolic y-offset
            y_offset = (relative_pos ** 2) * 8  # Quadratic curve for 3D depth effect

            # Target scale factor based on distance from center
            if relative_pos == 0:
                target_scale = 1.0  # Center item
                item.set_selected(True)
            else:
                # Smooth exponential falloff for scale
                distance = abs(relative_pos)
                target_scale = max(0.55, 1.0 - distance * 0.18)
                item.set_selected(False)

            # Target position
            target_width = int(200 * target_scale)
            target_height = int(200 * target_scale)
            target_x = center_x + x_offset - target_width // 2
            target_y = center_y + y_offset - target_height // 2

            # Animate position
            position_animation = QPropertyAnimation(item, b"geometry")
            position_animation.setDuration(self.animation_duration)
            position_animation.setStartValue(item.geometry())
            position_animation.setEndValue(QRect(target_x, target_y, target_width, target_height))
            position_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

            # Animate scale
            scale_animation = QPropertyAnimation(item, b"animated_scale")
            scale_animation.setDuration(self.animation_duration)
            scale_animation.setStartValue(item.animated_scale)
            scale_animation.setEndValue(target_scale)
            scale_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

            self.animation_group.addAnimation(position_animation)
            self.animation_group.addAnimation(scale_animation)

        # If no animations were added, fall back to immediate update
        if self.animation_group.animationCount() == 0:
            self.is_animating = False
            logger.debug("No animations added, falling back to immediate update")
            self._update_wheel_display_immediate()
            return

        # Connect animation finished signal
        self.animation_group.finished.connect(self._on_animation_finished)

        # Don't update media immediately - wait for animation to finish
        # This prevents rapid media changes when scrolling quickly

        # Safety timeout to reset animation flag if animation doesn't complete
        QTimer.singleShot(self.animation_duration + 100, self._animation_safety_reset)

        # Start the animation
        self.animation_group.start()

    def _on_animation_finished(self):
        """Called when wheel animation finishes"""
        self.is_animating = False

        # Start delayed media update timer
        # This ensures media only updates after wheel stops moving
        self.media_update_timer.start(self.media_update_delay)

    def _delayed_media_update(self):
        """Update media after wheel has stopped moving"""
        self.logger.debug("Delayed media update triggered")
        self.update_table_info()

    def _animation_safety_reset(self):
        """Safety reset for animation flag in case animation doesn't complete properly"""
        if self.is_animating:
            logger.debug("Animation safety reset triggered - forcing is_animating to False")
            self.is_animating = False
            # Also trigger delayed media update if it hasn't been triggered yet
            if not self.media_update_timer.isActive():
                self.media_update_timer.start(self.media_update_delay)

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

    def update_table_info(self):
        """Update the table information display"""
        if not self.tables or self.current_index >= len(self.tables):
            self.table_name_label.setText("No Tables Available")
            self.table_info_label.setText("")
            self.table_metadata_label.setText("")
            self.stop_background_video()
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

        # Emit highlighted signal
        self.table_highlighted.emit(table)

    def move_wheel_left(self):
        """Move wheel selection to the left with animation (wraps around)"""
        if not self.tables:
            return

        if self.current_index > 0:
            self.current_index -= 1
        else:
            # Wrap to end of list
            self.current_index = len(self.tables) - 1

        self.update_wheel_display(animate=True)

    def move_wheel_right(self):
        """Move wheel selection to the right with animation (wraps around)"""
        if not self.tables:
            return

        if self.current_index < len(self.tables) - 1:
            self.current_index += 1
        else:
            # Wrap to beginning of list
            self.current_index = 0

        self.update_wheel_display(animate=True)

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

        info_top_y = None
        info_height = 120
        if hasattr(self, 'info_widget') and self.info_widget.height() > 0:
            info_height = self.info_widget.height()

        # Info panel placement
        if hasattr(self, 'info_proxy'):
            info_width = max(0, min(600, max(0, width - 40)))
            info_x = (width - info_width) / 2 if width >= info_width else 0
            info_top_y = height - 140 if height >= 140 else max(0, height - info_height)
            self.info_proxy.setGeometry(QRectF(info_x, info_top_y, info_width, info_height))
            self.info_widget.resize(int(info_width), info_height)

        # Wheel container placement - extend to just above info panel with 20px gap
        if hasattr(self, 'wheel_proxy'):
            # Use half width of the screen, centered
            wheel_width = width * 0.5
            wheel_x = (width - wheel_width) / 2

            # Extend container from top to 20px above info panel
            top_margin = 20.0
            gap_before_info = 20.0
            wheel_y = top_margin
            # Wheel bottom = info_top - gap = (height - 140) - 20 = height - 160
            # wheel_height = (height - 160) - top_margin = height - 180
            wheel_height = height - 180

            self.wheel_proxy.setGeometry(QRectF(wheel_x, wheel_y, wheel_width, wheel_height))
            self.wheel_container.resize(int(wheel_width), int(wheel_height))

            # Update wheel background size to match container (extends to bottom)
            if hasattr(self, 'wheel_background'):
                self.wheel_background.setGeometry(0, 0, int(wheel_width), int(wheel_height))

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
        # Stop all timers to prevent hanging
        if hasattr(self, 'media_update_timer'):
            self.media_update_timer.stop()

        if hasattr(self, 'wheel_background') and self.wheel_background:
            if hasattr(self.wheel_background, 'glow_timer'):
                self.wheel_background.glow_timer.stop()

        # Stop loading popup timers if they exist
        # The loading popup might not exist as it's created dynamically
        for child in self.findChildren(LoadingPopup):
            if hasattr(child, 'spinner_timer'):
                child.spinner_timer.stop()
            if hasattr(child, 'fade_timer'):
                child.fade_timer.stop()
            if hasattr(child, 'fade_out_timer'):
                child.fade_out_timer.stop()

        # Stop animation group
        if hasattr(self, 'animation_group') and self.animation_group:
            self.animation_group.stop()
            try:
                self.animation_group.finished.disconnect()
            except:
                pass

        # Stop background video and clean up media player
        if hasattr(self, 'background_media_player'):
            self.background_media_player.stop()
            self.background_media_player.setSource(QUrl())
            self.background_media_player.setVideoOutput(None)
            self.background_media_player.setAudioOutput(None)

        # Clean up audio output
        if hasattr(self, 'background_audio_output'):
            self.background_audio_output = None

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

        self.setup_ui()
        self.load_tables()

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

            # Initialize media manager for finding media files
            from ..media.manager import MediaManager
            media_manager = MediaManager(self.config)

            # Convert Table models to dict format
            table_data = []
            for table in tables:
                # Find media files for this table using media manager
                media_files = media_manager.find_table_media(
                    table.name,
                    table.manufacturer or '',
                    table.year
                )

                # Find wheel image from media system
                wheel_image_path = ''
                if hasattr(table, 'wheel_image') and table.wheel_image:
                    wheel_image_path = table.wheel_image
                elif media_files.get('wheel_image'):
                    wheel_image_path = media_files['wheel_image']
                elif table.playfield_image:
                    wheel_image_path = table.playfield_image

                # If no direct wheel image, try to find one in the wheel images directory
                if not wheel_image_path:
                    from pathlib import Path
                    media_wheel_dir = Path(self.config.vpx.media_directory) / "images" / "wheel"
                    if media_wheel_dir.exists():
                        # Try to find a wheel image that matches the table name
                        table_name_clean = table.name.replace(':', '').replace('/', '').replace('\\', '')
                        for ext in ['.png', '.jpg', '.jpeg']:
                            wheel_file = media_wheel_dir / f"{table_name_clean}{ext}"
                            if wheel_file.exists():
                                wheel_image_path = str(wheel_file)
                                break
                            # Try with manufacturer and year
                            if table.manufacturer and table.year:
                                wheel_file = media_wheel_dir / f"{table_name_clean} ({table.manufacturer} {table.year}){ext}"
                                if wheel_file.exists():
                                    wheel_image_path = str(wheel_file)
                                    break

                # Get table video from media files
                table_video_path = ''
                if media_files.get('table_video'):
                    table_video_path = media_files['table_video']
                elif table.table_video:
                    table_video_path = table.table_video

                # Get playfield image from media files or database
                playfield_image_path = media_files.get('table_image', table.playfield_image or '')

                data = {
                    'id': table.id,
                    'name': table.name,
                    'manufacturer': table.manufacturer or '',
                    'year': table.year or '',
                    'file_path': table.file_path,
                    'wheel_image': wheel_image_path,
                    'image': playfield_image_path,  # playfield image for background
                    'table_video': table_video_path,
                    'backglass_image': media_files.get('backglass_image', table.backglass_image or ''),
                    'backglass_video': media_files.get('backglass_video', table.backglass_video or ''),
                    'dmd_image': media_files.get('dmd_image', table.dmd_image or ''),
                    'dmd_video': media_files.get('dmd_video', table.dmd_video or ''),
                    'table_audio': media_files.get('table_audio', ''),
                    'launch_audio': media_files.get('launch_audio', table.launch_audio or ''),
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

    def on_table_highlighted(self, table_data: dict):
        """Handle table highlight change from wheel"""
        table_name = table_data.get('name', 'Unknown')

        # Play navigation sound
        self._play_navigation_sound()

        # Play table audio if enabled and available, otherwise stop any playing audio
        if self.config.audio.table_audio:
            table_audio = table_data.get('table_audio', '')
            if table_audio:
                self.table_audio_player.play_once(table_audio)
                self.logger.debug(f"Playing table audio: {table_audio}")
            else:
                # Stop table audio if no audio is available for this table
                if self.table_audio_player.is_playing():
                    self.table_audio_player.stop()
                    self.logger.debug("Stopped table audio - no audio for this table")

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
        """Handle table launched - blank all displays during gameplay"""
        self.logger.info(f"Table launched, clearing displays for gameplay")

        # Stop input polling to avoid interfering with VPX input
        if self.input_manager:
            self.input_manager.stop_polling()
            self.logger.info("Stopped input polling - VPX will handle all input")

        # Hide loading screen on backglass
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

        # Restart input polling for frontend navigation
        if self.input_manager:
            self.input_manager.start_polling()
            self.logger.info("Restarted input polling - PinballUX controls active")

        # Restore the current table's display content
        if self.wheel_widget and self.wheel_widget.tables and 0 <= self.wheel_widget.current_index < len(self.wheel_widget.tables):
            current_table = self.wheel_widget.tables[self.wheel_widget.current_index]
            self.on_table_highlighted(current_table)

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
        # Clean up audio players
        if hasattr(self, 'audio_player'):
            self.audio_player.stop()
        if hasattr(self, 'nav_audio_player'):
            self.nav_audio_player.stop()
        if hasattr(self, 'table_audio_player'):
            self.table_audio_player.stop()

        # Clean up input manager
        if hasattr(self, 'input_manager'):
            self.input_manager.cleanup()

        # Clean up wheel widget media players
        if hasattr(self, 'wheel_widget'):
            try:
                self.wheel_widget.stop_background_video()
                # Clean up background media player
                if hasattr(self.wheel_widget, 'background_media_player'):
                    self.wheel_widget.background_media_player.stop()
                    self.wheel_widget.background_media_player.setSource(QUrl())
                    self.wheel_widget.background_media_player.setVideoOutput(None)
                    self.wheel_widget.background_media_player.setAudioOutput(None)
                if hasattr(self.wheel_widget, 'background_audio_output'):
                    self.wheel_widget.background_audio_output = None
                if hasattr(self.wheel_widget, 'background_video_item'):
                    self.wheel_widget.background_video_item.setParent(None)
                    self.wheel_widget.background_video_item = None
            except Exception as e:
                pass  # Ignore cleanup errors

        super().closeEvent(event)
