"""
Media widgets for displaying images and videos in PinballUX
"""

from PyQt6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout,
                             QFrame, QSizePolicy, QPushButton)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QPainter, QBrush, QColor
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from pathlib import Path
from typing import Optional, Union

from ..core.logger import get_logger

logger = get_logger(__name__)


class AudioPlayer(QWidget):
    """Widget for playing audio files (sound effects, music, etc.)"""

    playback_started = pyqtSignal()
    playback_stopped = pyqtSignal()
    playback_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_player = None
        self.audio_output = None
        self.current_audio_path = None
        self.setup_audio_player()

    def setup_audio_player(self):
        """Initialize the audio player"""
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)

        # Connect media player to audio output
        self.media_player.setAudioOutput(self.audio_output)

        # Connect signals
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_error_occurred)

    def load_audio(self, audio_path: str) -> bool:
        """Load an audio file"""
        try:
            if not Path(audio_path).exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False

            # Clear previous source before loading new audio
            self.media_player.stop()
            self.media_player.setSource(QUrl())

            self.current_audio_path = audio_path
            media_url = QUrl.fromLocalFile(str(Path(audio_path).resolve()))
            self.media_player.setSource(media_url)

            logger.info(f"Loaded audio: {audio_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load audio {audio_path}: {e}")
            return False

    def play(self):
        """Start audio playback"""
        if self.media_player:
            self.media_player.play()

    def play_once(self, audio_path: str = None):
        """Load and play audio file once"""
        if audio_path:
            if not self.load_audio(audio_path):
                return False
        self.play()
        return True

    def pause(self):
        """Pause audio playback"""
        if self.media_player:
            self.media_player.pause()

    def stop(self):
        """Stop audio playback"""
        if self.media_player:
            self.media_player.stop()

    def cleanup(self):
        """Clean up media player resources"""
        try:
            if self.media_player:
                self.media_player.stop()
                self.media_player.setSource(QUrl())
                self.media_player.setAudioOutput(None)
                self.media_player = None
            if self.audio_output:
                self.audio_output = None
        except Exception as e:
            pass  # Ignore cleanup errors

    def set_volume(self, volume: float):
        """Set audio volume (0.0 to 1.0)"""
        if self.audio_output:
            self.audio_output.setVolume(volume)

    def set_muted(self, muted: bool):
        """Set audio mute state"""
        if self.audio_output:
            self.audio_output.setMuted(muted)

    def get_volume(self) -> float:
        """Get current volume (0.0 to 1.0)"""
        if self.audio_output:
            return self.audio_output.volume()
        return 0.0

    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        if self.media_player:
            return self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        return False

    def _on_playback_state_changed(self, state):
        """Handle playback state changes"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.playback_started.emit()
            logger.debug(f"Audio playback started: {self.current_audio_path}")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.playback_stopped.emit()
            logger.debug(f"Audio playback stopped: {self.current_audio_path}")

    def _on_media_status_changed(self, status):
        """Handle media status changes"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.playback_finished.emit()
            logger.debug(f"Audio playback finished: {self.current_audio_path}")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error(f"Invalid audio media: {self.current_audio_path}")

    def _on_error_occurred(self, error, error_string):
        """Handle media player errors"""
        logger.error(f"Audio player error: {error_string}")

    def clear_audio(self):
        """Clear the current audio"""
        self.stop()
        self.current_audio_path = None
        self.media_player.setSource(QUrl())


class MediaDisplayWidget(QFrame):
    """Base widget for displaying media (images or videos)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_media_path = None
        self.media_type = None
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI layout"""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setStyleSheet("QFrame { background-color: black; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Default content when no media is loaded
        self.default_label = QLabel("No Media")
        self.default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_label.setStyleSheet("color: white; font-size: 16px;")
        layout.addWidget(self.default_label)

    def clear_media(self):
        """Clear current media and show default content"""
        self.current_media_path = None
        self.media_type = None
        self.default_label.show()

    def load_media(self, media_path: str):
        """Load media file (image or video)"""
        if not media_path or not Path(media_path).exists():
            self.clear_media()
            return False

        self.current_media_path = media_path
        file_ext = Path(media_path).suffix.lower()

        # Determine media type
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'}
        video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm', '.f4v', '.flv'}

        if file_ext in image_extensions:
            return self._load_image(media_path)
        elif file_ext in video_extensions:
            return self._load_video(media_path)
        else:
            logger.warning(f"Unsupported media format: {file_ext}")
            self.clear_media()
            return False

    def _load_image(self, image_path: str) -> bool:
        """Load and display an image"""
        # This will be implemented by subclasses
        return False

    def _load_video(self, video_path: str) -> bool:
        """Load and display a video"""
        # This will be implemented by subclasses
        return False


class ImageWidget(QLabel):
    """Widget for displaying images with proper scaling"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)
        self.setStyleSheet("background-color: black;")

    def load_image(self, image_path: str) -> bool:
        """Load an image file"""
        try:
            if not Path(image_path).exists():
                return False

            self.original_pixmap = QPixmap(image_path)
            if self.original_pixmap.isNull():
                return False

            self._update_scaled_pixmap()
            return True

        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {e}")
            return False

    def _update_scaled_pixmap(self):
        """Update the displayed pixmap with proper scaling"""
        if not self.original_pixmap:
            return

        # Scale pixmap to fit widget while maintaining aspect ratio
        scaled_pixmap = self.original_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """Handle widget resize events"""
        super().resizeEvent(event)
        if self.original_pixmap:
            self._update_scaled_pixmap()

    def clear_image(self):
        """Clear the current image"""
        self.original_pixmap = None
        self.clear()


class VideoWidget(QWidget):
    """Widget for displaying videos using QMediaPlayer"""

    playback_started = pyqtSignal()
    playback_stopped = pyqtSignal()
    playback_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_player = None
        self.audio_output = None
        self.video_widget = None
        self.current_video_path = None
        self.scale_small_videos = False
        self.min_video_width = 512
        self.setup_media_player()
        self.setup_ui()

    def setup_media_player(self):
        """Initialize the media player"""
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.video_widget = QVideoWidget(self)

        # Connect media player to audio and video outputs
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        # Connect signals
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_error_occurred)
        self.media_player.metaDataChanged.connect(self._on_metadata_changed)

    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add video widget
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Keep aspect ratio to prevent stretching/blur
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        layout.addWidget(self.video_widget)

        # Set background color
        self.setStyleSheet("background-color: black;")

    def load_video(self, video_path: str, scale_small_videos: bool = False, min_width: int = 512) -> bool:
        """Load a video file

        Args:
            video_path: Path to the video file
            scale_small_videos: If True, scale up videos smaller than min_width by 2x
            min_width: Minimum width threshold for scaling (default 512px)
        """
        try:
            if not Path(video_path).exists():
                logger.error(f"Video file not found: {video_path}")
                return False

            # Clear previous source before loading new video
            self.media_player.stop()
            self.media_player.setSource(QUrl())

            self.current_video_path = video_path
            media_url = QUrl.fromLocalFile(str(Path(video_path).resolve()))
            self.media_player.setSource(media_url)

            # If scaling is enabled, check video dimensions and apply 2x scale for small videos
            if scale_small_videos:
                self._apply_scaling_if_needed(video_path, min_width)

            logger.info(f"Loaded video: {video_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load video {video_path}: {e}")
            return False

    def _apply_scaling_if_needed(self, video_path: str, min_width: int):
        """Check video dimensions and apply 2x scaling if video is small"""
        try:
            from PyQt6.QtMultimedia import QMediaMetaData

            # Get video resolution from metadata when available
            # We'll handle this in the metadata changed callback
            self.min_video_width = min_width

        except Exception as e:
            logger.warning(f"Could not check video dimensions: {e}")

    def _on_metadata_changed(self):
        """Handle metadata changes to check video dimensions"""
        if not self.scale_small_videos or not self.media_player:
            return

        try:
            from PyQt6.QtMultimedia import QMediaMetaData

            # Try to get video resolution
            resolution = self.media_player.metaData().value(QMediaMetaData.Key.Resolution)

            if resolution:
                width = resolution.width()
                height = resolution.height()
                logger.info(f"Video resolution: {width}x{height}")

                # If video is smaller than threshold, set minimum size to scale it 2x
                if width < self.min_video_width:
                    min_size_width = width * 2
                    min_size_height = height * 2
                    self.video_widget.setMinimumSize(min_size_width, min_size_height)
                    logger.info(f"Scaling small video 2x: {min_size_width}x{min_size_height}")
                else:
                    # Reset to no minimum size
                    self.video_widget.setMinimumSize(0, 0)

        except Exception as e:
            logger.warning(f"Could not apply video scaling: {e}")

    def play(self):
        """Start video playback"""
        if self.media_player:
            self.media_player.play()

    def pause(self):
        """Pause video playback"""
        if self.media_player:
            self.media_player.pause()

    def stop(self):
        """Stop video playback"""
        if self.media_player:
            self.media_player.stop()

    def cleanup(self):
        """Clean up media player resources"""
        try:
            if self.media_player:
                self.media_player.stop()
                self.media_player.setSource(QUrl())
                self.media_player.setVideoOutput(None)
                self.media_player.setAudioOutput(None)
                self.media_player = None
            if self.audio_output:
                self.audio_output = None
            if self.video_widget:
                self.video_widget.setParent(None)
                self.video_widget = None
        except Exception as e:
            pass  # Ignore cleanup errors

    def set_volume(self, volume: float):
        """Set audio volume (0.0 to 1.0)"""
        if self.audio_output:
            self.audio_output.setVolume(volume)

    def set_muted(self, muted: bool):
        """Set audio mute state"""
        if self.audio_output:
            self.audio_output.setMuted(muted)

    def set_position(self, position_ms: int):
        """Set playback position in milliseconds"""
        if self.media_player:
            self.media_player.setPosition(position_ms)

    def get_position(self) -> int:
        """Get current playback position in milliseconds"""
        if self.media_player:
            return self.media_player.position()
        return 0

    def get_duration(self) -> int:
        """Get total video duration in milliseconds"""
        if self.media_player:
            return self.media_player.duration()
        return 0

    def is_playing(self) -> bool:
        """Check if video is currently playing"""
        if self.media_player:
            return self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        return False

    def _on_playback_state_changed(self, state):
        """Handle playback state changes"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.playback_started.emit()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.playback_stopped.emit()

    def _on_media_status_changed(self, status):
        """Handle media status changes"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.playback_finished.emit()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.error(f"Invalid media: {self.current_video_path}")

    def _on_error_occurred(self, error, error_string):
        """Handle media player errors"""
        logger.error(f"Media player error: {error_string}")

    def clear_video(self):
        """Clear the current video"""
        self.stop()
        self.current_video_path = None
        self.media_player.setSource(QUrl())


class TableMediaWidget(MediaDisplayWidget):
    """Widget for displaying table media (images and videos)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_widget = None
        self.video_widget = None
        self.current_widget = None
        self.setup_media_widgets()

    def setup_media_widgets(self):
        """Setup image and video widgets"""
        # Clear default layout
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Create media widgets
        self.image_widget = ImageWidget(self)
        self.video_widget = VideoWidget(self)

        # Initially hide both
        self.image_widget.hide()
        self.video_widget.hide()

        # Add to layout
        layout.addWidget(self.image_widget)
        layout.addWidget(self.video_widget)
        layout.addWidget(self.default_label)

    def _load_image(self, image_path: str) -> bool:
        """Load and display an image"""
        if self.image_widget.load_image(image_path):
            self._switch_to_image()
            self.media_type = 'image'
            logger.info(f"Loaded image: {image_path}")
            return True
        return False

    def _load_video(self, video_path: str) -> bool:
        """Load and display a video"""
        if self.video_widget.load_video(video_path):
            self._switch_to_video()
            self.media_type = 'video'
            logger.info(f"Loaded video: {video_path}")
            return True
        return False

    def _switch_to_image(self):
        """Switch display to image widget"""
        if self.current_widget:
            self.current_widget.hide()
        self.image_widget.show()
        self.current_widget = self.image_widget
        self.default_label.hide()

    def _switch_to_video(self):
        """Switch display to video widget"""
        if self.current_widget:
            self.current_widget.hide()
        self.video_widget.show()
        self.current_widget = self.video_widget
        self.default_label.hide()

    def play_video(self):
        """Start video playback if current media is video"""
        if self.media_type == 'video' and self.video_widget:
            self.video_widget.play()

    def pause_video(self):
        """Pause video playback if current media is video"""
        if self.media_type == 'video' and self.video_widget:
            self.video_widget.pause()

    def stop_video(self):
        """Stop video playback if current media is video"""
        if self.media_type == 'video' and self.video_widget:
            self.video_widget.stop()

    def set_video_volume(self, volume: float):
        """Set video volume"""
        if self.video_widget:
            self.video_widget.set_volume(volume)

    def clear_media(self):
        """Clear current media and show default content"""
        super().clear_media()
        if self.image_widget:
            self.image_widget.clear_image()
        if self.video_widget:
            self.video_widget.clear_video()
        if self.current_widget:
            self.current_widget.hide()
        self.current_widget = None
        self.default_label.show()


class AttractModeWidget(TableMediaWidget):
    """Widget for attract mode with automatic video cycling"""

    video_changed = pyqtSignal(str)  # Emitted when video changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_list = []
        self.current_video_index = 0
        self.cycle_timer = QTimer(self)
        self.cycle_timer.timeout.connect(self.next_video)
        self.cycle_interval = 10000  # 10 seconds default

        # Connect video signals
        if self.video_widget:
            self.video_widget.playback_finished.connect(self.next_video)

    def set_video_list(self, video_paths: list):
        """Set list of videos for attract mode"""
        self.video_list = [path for path in video_paths if Path(path).exists()]
        self.current_video_index = 0

    def start_attract_mode(self, cycle_interval_ms: int = 10000):
        """Start attract mode with automatic video cycling"""
        if not self.video_list:
            return False

        self.cycle_interval = cycle_interval_ms
        self.current_video_index = 0

        if self.load_current_video():
            self.play_video()
            self.cycle_timer.start(self.cycle_interval)
            return True
        return False

    def stop_attract_mode(self):
        """Stop attract mode"""
        self.cycle_timer.stop()
        self.stop_video()

    def next_video(self):
        """Switch to next video in the list"""
        if not self.video_list:
            return

        self.stop_video()
        self.current_video_index = (self.current_video_index + 1) % len(self.video_list)

        if self.load_current_video():
            self.play_video()
            self.video_changed.emit(self.video_list[self.current_video_index])

    def previous_video(self):
        """Switch to previous video in the list"""
        if not self.video_list:
            return

        self.stop_video()
        self.current_video_index = (self.current_video_index - 1) % len(self.video_list)

        if self.load_current_video():
            self.play_video()
            self.video_changed.emit(self.video_list[self.current_video_index])

    def load_current_video(self) -> bool:
        """Load the current video from the list"""
        if not self.video_list or self.current_video_index >= len(self.video_list):
            return False

        video_path = self.video_list[self.current_video_index]
        return self.load_media(video_path)