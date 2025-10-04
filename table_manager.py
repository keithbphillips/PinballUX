#!/usr/bin/env python3
"""
PinballUX - Table Manager
GUI application for managing tables, downloading media from ftp.gameex.com, and scanning tables
"""

import sys
import os
from pathlib import Path
from ftplib import FTP
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import json
import base64
import shutil
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QSplitter, QTextEdit, QProgressBar, QMessageBox, QGroupBox, QDialog,
    QListWidget, QListWidgetItem, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QMovie
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pinballux.src.core.config import Config
from pinballux.src.database.models import DatabaseManager
from pinballux.src.database.service import TableService
from pinballux.src.database.table_manager import TableManager as TableScanner


@dataclass
class DownloadedFile:
    """Represents a downloaded file"""
    media_type: str
    temp_path: Path
    ftp_filename: str
    table_name: str
    status: str = "pending"  # pending, saved, skipped


def similarity_ratio(str1: str, str2: str) -> float:
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def get_credentials_file(config_dir: Path) -> Path:
    """Get path to FTP credentials file"""
    return config_dir / "ftp_credentials.json"


def save_credentials(config_dir: Path, username: str, password: str) -> None:
    """Save FTP credentials to config file"""
    creds_file = get_credentials_file(config_dir)
    encoded_password = base64.b64encode(password.encode()).decode()
    credentials = {
        "host": "ftp.gameex.com",
        "username": username,
        "password": encoded_password
    }
    with open(creds_file, 'w') as f:
        json.dump(credentials, f, indent=2)
    os.chmod(creds_file, 0o600)


def load_credentials(config_dir: Path) -> Optional[Tuple[str, str]]:
    """Load FTP credentials from config file"""
    creds_file = get_credentials_file(config_dir)
    if not creds_file.exists():
        return None
    try:
        with open(creds_file, 'r') as f:
            credentials = json.load(f)
        username = credentials.get("username")
        encoded_password = credentials.get("password")
        if not username or not encoded_password:
            return None
        password = base64.b64decode(encoded_password).decode()
        return (username, password)
    except:
        return None


def match_file_to_table(filename: str, table) -> float:
    """Match a filename to a table, return similarity score"""
    clean_filename = Path(filename).stem
    filename_title = clean_filename.split('(')[0].strip()
    table_title = table.name.split('(')[0].strip()
    return similarity_ratio(filename_title, table_title)


def get_local_media_path(media_type: str, filename: str) -> Path:
    """Get the local path for a media file based on type"""
    base_path = Path(project_root) / "pinballux" / "data" / "media"
    ext = Path(filename).suffix.lower()

    if media_type == 'launch_audio':
        return base_path / "audio" / "launch" / filename
    elif media_type == 'table_audio':
        return base_path / "audio" / "table" / filename
    elif media_type == 'backglass':
        if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            return base_path / "videos" / "backglass" / filename
        else:
            return base_path / "images" / "backglass" / filename
    elif media_type == 'table':
        if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            return base_path / "videos" / "table" / filename
        else:
            return base_path / "images" / "table" / filename
    elif media_type == 'dmd':
        if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            return base_path / "videos" / "real_dmd_color" / filename
        else:
            return base_path / "images" / "dmd" / filename
    elif media_type == 'topper':
        if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            return base_path / "videos" / "topper" / filename
        else:
            return base_path / "images" / "topper" / filename
    elif media_type == 'wheel':
        return base_path / "images" / "wheel" / filename
    else:
        return base_path / "images" / media_type / filename


class FTPDownloadThread(QThread):
    """Thread for FTP download operations"""
    progress = pyqtSignal(str)  # Status messages
    file_downloaded = pyqtSignal(str, str, str, str)  # media_type, temp_path, ftp_filename, table_name
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, username: str, password: str, table, config_dir: Path):
        super().__init__()
        self.username = username
        self.password = password
        self.table = table
        self.config_dir = config_dir
        self.temp_dir = Path(project_root) / "ftp_downloads_temp"

    def run(self):
        try:
            # Create temp directory
            self.temp_dir.mkdir(exist_ok=True)

            # Connect to FTP
            self.progress.emit("Connecting to ftp.gameex.com...")
            ftp = FTP("ftp.gameex.com")
            ftp.encoding = 'latin-1'
            ftp.login(self.username, self.password)
            self.progress.emit("✓ Connected and logged in")

            # Get media directories
            base_path = "/-PinballX-/Media/Visual Pinball"
            media_dirs = self.get_media_subdirectories(ftp, base_path)

            # Download matching files
            download_count = 0
            for media_type, directories in media_dirs.items():
                for directory in directories:
                    files = self.list_media_files(ftp, directory)
                    if not files:
                        continue

                    for filename in files:
                        score = match_file_to_table(filename, self.table)

                        # Check for substring match
                        file_title = Path(filename).stem.split('(')[0].strip().lower()
                        table_title = self.table.name.split('(')[0].strip().lower()
                        is_substring_match = table_title in file_title or file_title in table_title

                        if score >= 0.90 or is_substring_match:
                            # Download to temp directory with media type structure
                            media_type_dir = self.temp_dir / media_type
                            media_type_dir.mkdir(exist_ok=True)

                            temp_path = media_type_dir / filename

                            if temp_path.exists():
                                # File already in cache, skip download but still add to list
                                self.progress.emit(f"⚡ Cached: {filename}")
                                self.file_downloaded.emit(media_type, str(temp_path), filename, self.table.name)
                            else:
                                # Download file
                                ftp.cwd(directory)
                                with open(temp_path, 'wb') as f:
                                    ftp.retrbinary(f'RETR {filename}', f.write)

                                download_count += 1
                                self.progress.emit(f"✓ Downloaded: {filename}")
                                self.file_downloaded.emit(media_type, str(temp_path), filename, self.table.name)

            ftp.quit()
            self.finished.emit(True, f"Downloaded {download_count} files")

        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

    def get_media_subdirectories(self, ftp: FTP, base_path: str) -> Dict[str, List[str]]:
        """Get media subdirectories"""
        dir_mapping = {
            'backglass': ['Backglass Images', 'Backglass Videos'],
            'dmd': ['DMD Color Videos', 'DMD Images', 'DMD Videos', 'FullDMD Videos',
                    'Real DMD Color Images', 'Real DMD Color Videos', 'Real DMD Images', 'Real DMD Videos'],
            'table': ['Table Images', 'table video', 'Table Videos'],
            'topper': ['Topper Images', 'Topper Videos'],
            'wheel': ['Wheel Images'],
            'launch_audio': ['Launch Audio'],
            'table_audio': ['Table Audio']
        }

        subdirs = {}
        for media_type, dir_names in dir_mapping.items():
            for dir_name in dir_names:
                full_path = f"{base_path}/{dir_name}"
                if media_type not in subdirs:
                    subdirs[media_type] = []
                subdirs[media_type].append(full_path)

        return subdirs

    def list_media_files(self, ftp: FTP, directory: str) -> List[str]:
        """List media files in an FTP directory"""
        try:
            ftp.cwd(directory)
            all_items = ftp.nlst()

            media_extensions = {
                '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif',
                '.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm',
                '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'
            }

            files = []
            for name in all_items:
                ext = Path(name).suffix.lower()
                if ext in media_extensions:
                    files.append(name)

            return files
        except:
            return []


class TableSelectorDialog(QDialog):
    """Dialog for selecting a table from the database"""

    def __init__(self, tables, parent=None):
        super().__init__(parent)
        self.tables = tables
        self.selected_table = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Select Table")
        self.setMinimumSize(500, 600)

        layout = QVBoxLayout()

        # Search field
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.filter_tables)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Table list
        self.table_list = QListWidget()
        self.table_list.itemDoubleClicked.connect(self.on_table_selected)
        layout.addWidget(self.table_list)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # Populate list
        self.populate_tables()

    def populate_tables(self, filter_text=""):
        """Populate the table list"""
        self.table_list.clear()

        for table in self.tables:
            if filter_text.lower() in table.name.lower():
                item = QListWidgetItem(table.name)
                item.setData(Qt.ItemDataRole.UserRole, table)
                self.table_list.addItem(item)

    def filter_tables(self, text):
        """Filter tables based on search text"""
        self.populate_tables(text)

    def on_table_selected(self, item):
        """Handle table selection"""
        self.selected_table = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def accept(self):
        """Handle OK button"""
        current_item = self.table_list.currentItem()
        if current_item:
            self.selected_table = current_item.data(Qt.ItemDataRole.UserRole)
        super().accept()


class MediaReviewWidget(QWidget):
    """Widget for reviewing downloaded media files"""

    def __init__(self):
        super().__init__()
        self.files: List[DownloadedFile] = []
        self.current_file: Optional[DownloadedFile] = None
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        # Left panel - File tree
        left_panel = QVBoxLayout()

        # Buttons at top
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_current)
        self.save_btn.setEnabled(False)
        self.delete_all_btn = QPushButton("Delete All")
        self.delete_all_btn.clicked.connect(self.delete_all)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.delete_all_btn)
        left_panel.addLayout(button_layout)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Downloaded Files")
        self.file_tree.itemClicked.connect(self.on_file_selected)
        self.file_tree.header().setStretchLastSection(True)
        self.file_tree.setColumnCount(1)
        left_panel.addWidget(self.file_tree)

        # Middle panel - Downloaded file preview
        middle_panel = QVBoxLayout()
        middle_panel.setSpacing(0)
        middle_title = QLabel("Downloaded File Preview")
        middle_title.setFixedHeight(20)
        middle_panel.addWidget(middle_title)

        self.downloaded_preview = QWidget()
        self.downloaded_preview.setMinimumHeight(400)
        self.downloaded_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.downloaded_preview_layout = QVBoxLayout()
        self.downloaded_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.downloaded_preview_layout.setSpacing(0)
        self.downloaded_preview.setLayout(self.downloaded_preview_layout)

        self.downloaded_image_label = QLabel("Select a file to preview")
        self.downloaded_image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.downloaded_image_label.setMinimumSize(400, 400)
        self.downloaded_image_label.setScaledContents(False)
        self.downloaded_image_label.mousePressEvent = lambda e: self.play_downloaded_media()

        self.downloaded_video_widget = QVideoWidget()
        self.downloaded_video_widget.setMinimumSize(400, 300)
        self.downloaded_video_widget.hide()
        self.downloaded_video_widget.mousePressEvent = lambda e: self.play_downloaded_media()

        self.media_player.setVideoOutput(self.downloaded_video_widget)

        self.downloaded_preview_layout.addWidget(self.downloaded_image_label)
        self.downloaded_preview_layout.addWidget(self.downloaded_video_widget)

        middle_panel.addWidget(self.downloaded_preview)

        # Right panel - Existing file preview
        right_panel = QVBoxLayout()
        right_panel.setSpacing(0)
        right_title = QLabel("Existing PinballUX File (if any)")
        right_title.setFixedHeight(20)
        right_panel.addWidget(right_title)

        self.existing_preview = QWidget()
        self.existing_preview.setMinimumHeight(400)
        self.existing_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.existing_preview_layout = QVBoxLayout()
        self.existing_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.existing_preview_layout.setSpacing(0)
        self.existing_preview.setLayout(self.existing_preview_layout)

        self.existing_image_label = QLabel("No existing file")
        self.existing_image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.existing_image_label.setMinimumSize(400, 400)
        self.existing_image_label.setScaledContents(False)
        self.existing_image_label.mousePressEvent = lambda e: self.play_existing_media()

        self.existing_video_widget = QVideoWidget()
        self.existing_video_widget.setMinimumSize(400, 300)
        self.existing_video_widget.hide()
        self.existing_video_widget.mousePressEvent = lambda e: self.play_existing_media()

        self.existing_media_player = QMediaPlayer()
        self.existing_audio_output = QAudioOutput()
        self.existing_media_player.setAudioOutput(self.existing_audio_output)
        self.existing_media_player.setVideoOutput(self.existing_video_widget)

        self.existing_preview_layout.addWidget(self.existing_image_label)
        self.existing_preview_layout.addWidget(self.existing_video_widget)

        right_panel.addWidget(self.existing_preview)

        # Add panels to splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(20)  # Add spacing between panels
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        middle_widget = QWidget()
        middle_widget.setLayout(middle_panel)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)

        splitter.addWidget(left_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(right_widget)

        # Make panels resizable with initial sizes
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([300, 450, 450])  # Initial sizes
        splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing

        layout.addWidget(splitter)
        self.setLayout(layout)

    def add_file(self, media_type: str, temp_path: str, ftp_filename: str, table_name: str):
        """Add a downloaded file to the review list"""
        file = DownloadedFile(media_type, Path(temp_path), ftp_filename, table_name)
        self.files.append(file)
        self.update_file_tree()

    def clear_files(self):
        """Clear all files from the review list"""
        # Stop any playing media
        self.media_player.stop()
        self.existing_media_player.stop()

        # Clear files list
        self.files.clear()
        self.current_file = None

        # Reset UI
        self.file_tree.clear()
        self.downloaded_image_label.setText("Select a file to preview")
        self.downloaded_image_label.setPixmap(QPixmap())
        self.downloaded_image_label.show()
        self.downloaded_video_widget.hide()
        self.existing_image_label.setText("No existing file")
        self.existing_image_label.setPixmap(QPixmap())
        self.existing_image_label.show()
        self.existing_video_widget.hide()
        self.save_btn.setEnabled(False)

    def update_file_tree(self):
        """Update the file tree with current files"""
        self.file_tree.clear()

        # Group by media type
        media_types = {}
        for file in self.files:
            if file.media_type not in media_types:
                media_types[file.media_type] = []
            media_types[file.media_type].append(file)

        # Create tree items
        for media_type, files in sorted(media_types.items()):
            type_item = QTreeWidgetItem(self.file_tree, [media_type.upper()])
            type_item.setExpanded(True)

            for file in files:
                # Get file type icon
                ext = file.temp_path.suffix.lower()
                if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
                    type_icon = "🎬"
                elif ext in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}:
                    type_icon = "🖼️"
                elif ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                    type_icon = "🔊"
                else:
                    type_icon = "📄"

                status_icon = "✓" if file.status == "saved" else "✗" if file.status == "skipped" else "○"
                file_item = QTreeWidgetItem(type_item, [f"{status_icon} {type_icon} {file.ftp_filename}"])
                file_item.setData(0, Qt.ItemDataRole.UserRole, file)

        # Resize column to fit content
        self.file_tree.resizeColumnToContents(0)

    def on_file_selected(self, item: QTreeWidgetItem, column: int):
        """Handle file selection"""
        file = item.data(0, Qt.ItemDataRole.UserRole)
        if not file:
            return

        self.current_file = file
        self.save_btn.setEnabled(file.status == "pending")

        # Stop any playing media
        self.media_player.stop()
        self.existing_media_player.stop()

        # Show downloaded file preview
        self.show_downloaded_preview(file)

        # Show existing file preview
        self.show_existing_preview(file)

    def show_downloaded_preview(self, file: DownloadedFile):
        """Show preview of the downloaded file"""
        ext = file.temp_path.suffix.lower()

        if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            # Video
            self.downloaded_image_label.hide()
            self.downloaded_video_widget.show()
            self.media_player.setSource(QUrl.fromLocalFile(str(file.temp_path)))
            self.media_player.play()
        elif ext in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}:
            # Image
            self.downloaded_video_widget.hide()
            self.downloaded_image_label.show()
            pixmap = QPixmap(str(file.temp_path))
            # Scale to a fixed reasonable size
            scaled_pixmap = pixmap.scaled(400, 400,
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            self.downloaded_image_label.setPixmap(scaled_pixmap)
            self.downloaded_image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        elif ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
            # Audio
            self.downloaded_video_widget.hide()
            self.downloaded_image_label.show()
            self.downloaded_image_label.setText(f"🔊 Click to play: {file.ftp_filename}")

    def find_existing_file(self, file: DownloadedFile) -> Optional[Path]:
        """Find existing file of the same media type, regardless of extension"""
        base_path = Path(project_root) / "pinballux" / "data" / "media"

        # Define extension groups by media type
        video_exts = {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
        audio_exts = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}

        # Determine which extensions to search for
        downloaded_ext = file.temp_path.suffix.lower()
        if downloaded_ext in video_exts:
            search_exts = video_exts
        elif downloaded_ext in image_exts:
            search_exts = image_exts
        elif downloaded_ext in audio_exts:
            search_exts = audio_exts
        else:
            search_exts = {downloaded_ext}

        # For DMD files, check all DMD directories
        if file.media_type == 'dmd':
            if downloaded_ext in video_exts:
                dmd_dirs = ['videos/dmd', 'videos/fulldmd', 'videos/real_dmd', 'videos/real_dmd_color']
            else:
                dmd_dirs = ['images/dmd', 'images/real_dmd']

            for dmd_dir in dmd_dirs:
                for ext in search_exts:
                    local_filename = f"{file.table_name}{ext}"
                    local_path = base_path / dmd_dir / local_filename
                    if local_path.exists():
                        return local_path
        else:
            # Search for any matching file with the table name
            for ext in search_exts:
                local_filename = f"{file.table_name}{ext}"
                local_path = get_local_media_path(file.media_type, local_filename)
                if local_path.exists():
                    return local_path

        return None

    def show_existing_preview(self, file: DownloadedFile):
        """Show preview of the existing PinballUX file if it exists"""
        local_path = self.find_existing_file(file)

        if local_path:
            ext = local_path.suffix.lower()

            if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
                # Video
                self.existing_image_label.hide()
                self.existing_video_widget.show()
                self.existing_media_player.setSource(QUrl.fromLocalFile(str(local_path)))
                self.existing_media_player.play()
            elif ext in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}:
                # Image
                self.existing_video_widget.hide()
                self.existing_image_label.show()
                pixmap = QPixmap(str(local_path))
                # Scale to a fixed reasonable size
                scaled_pixmap = pixmap.scaled(400, 400,
                                              Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                self.existing_image_label.setPixmap(scaled_pixmap)
                self.existing_image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            elif ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                # Audio
                self.existing_video_widget.hide()
                self.existing_image_label.show()
                self.existing_image_label.setText(f"🔊 Click to play existing: {local_path.name}")
        else:
            # No existing file
            self.existing_video_widget.hide()
            self.existing_image_label.show()
            self.existing_image_label.setText("No existing file")
            self.existing_image_label.setPixmap(QPixmap())

    def play_downloaded_media(self):
        """Play downloaded audio when clicked"""
        if self.current_file:
            ext = self.current_file.temp_path.suffix.lower()
            if ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                self.media_player.setSource(QUrl.fromLocalFile(str(self.current_file.temp_path)))
                self.media_player.play()

    def play_existing_media(self):
        """Play existing audio when clicked"""
        if self.current_file:
            local_path = self.find_existing_file(self.current_file)

            if local_path:
                ext = local_path.suffix.lower()
                if ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                    self.existing_media_player.setSource(QUrl.fromLocalFile(str(local_path)))
                    self.existing_media_player.play()

    def save_current(self):
        """Save the current file to permanent location"""
        if not self.current_file:
            return

        # Generate local filename with table name
        local_filename = f"{self.current_file.table_name}{self.current_file.temp_path.suffix}"
        local_path = get_local_media_path(self.current_file.media_type, local_filename)

        # Check if any existing file exists (any extension of the same type)
        existing_file = self.find_existing_file(self.current_file)

        if existing_file:
            reply = QMessageBox.question(
                self,
                "File Exists",
                f"File already exists:\n{existing_file}\n\nThis will be replaced with:\n{local_path}\n\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                return

            # Delete the old file if it has a different extension
            if existing_file != local_path and existing_file.exists():
                existing_file.unlink()

        # Create directory and copy file
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.current_file.temp_path, local_path)

        # Mark as saved
        self.current_file.status = "saved"
        self.update_file_tree()
        self.save_btn.setEnabled(False)

        # Update the existing preview to show the newly saved file
        self.show_existing_preview(self.current_file)

        QMessageBox.information(self, "Saved", f"File saved to:\n{local_path}")

    def delete_all(self):
        """Delete all cached files for the current table"""
        reply = QMessageBox.question(self, "Confirm Delete",
                                     "Delete all cached files for this table?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for file in self.files:
                if file.temp_path.exists():
                    file.temp_path.unlink()
                    deleted_count += 1

            # Clear the files list and update UI
            self.files = []
            self.update_file_tree()
            self.downloaded_image_label.setText("Select a file to preview")
            self.downloaded_image_label.show()
            self.downloaded_video_widget.hide()
            self.existing_image_label.setText("No existing file")
            self.existing_image_label.show()
            self.existing_video_widget.hide()
            self.save_btn.setEnabled(False)

            QMessageBox.information(self, "Deleted", f"Deleted {deleted_count} cached files")


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.config_dir = Path(self.config.config_file).parent
        db_path = self.config_dir / "pinballux.db"
        self.db_manager = DatabaseManager(f"sqlite:///{db_path}")
        self.db_manager.initialize()
        self.table_service = TableService(self.db_manager)

        self.download_thread = None
        self.selected_table = None

        self.init_ui()
        self.load_saved_credentials()

        # Offer to scan tables on startup
        self.scan_tables_on_startup()

    def init_ui(self):
        self.setWindowTitle("PinballUX - Table Manager")
        self.setMinimumSize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Login section (only show if no saved credentials)
        self.login_group = QGroupBox("FTP Login")
        login_layout = QVBoxLayout()

        cred_layout = QHBoxLayout()
        cred_layout.addWidget(QLabel("Username:"))
        self.username_input = QLineEdit()
        cred_layout.addWidget(self.username_input)

        cred_layout.addWidget(QLabel("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        cred_layout.addWidget(self.password_input)

        self.save_creds_btn = QPushButton("Save Credentials")
        self.save_creds_btn.clicked.connect(self.save_credentials)
        cred_layout.addWidget(self.save_creds_btn)

        login_layout.addLayout(cred_layout)
        self.login_group.setLayout(login_layout)
        layout.addWidget(self.login_group)

        # Table selection
        table_group = QGroupBox("Table Selection")
        table_layout = QHBoxLayout()

        self.select_table_btn = QPushButton("Select Table...")
        self.select_table_btn.clicked.connect(self.show_table_selector)
        table_layout.addWidget(self.select_table_btn)

        self.selected_table_label = QLabel("No table selected")
        self.selected_table_label.setStyleSheet("font-weight: bold;")
        table_layout.addWidget(self.selected_table_label)

        table_layout.addStretch()

        self.download_btn = QPushButton("Download Media")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        table_layout.addWidget(self.download_btn)

        self.stop_btn = QPushButton("Stop Download")
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setEnabled(False)
        table_layout.addWidget(self.stop_btn)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Download status
        status_group = QGroupBox("Download Status")
        status_layout = QVBoxLayout()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        status_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.hide()
        status_layout.addWidget(self.progress_bar)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Progress log
        self.progress_text = QTextEdit()
        self.progress_text.setMaximumHeight(150)
        self.progress_text.setReadOnly(True)
        layout.addWidget(self.progress_text)

        # Media review widget
        self.media_review = MediaReviewWidget()
        layout.addWidget(self.media_review)

    def load_saved_credentials(self):
        """Load saved credentials if available"""
        creds = load_credentials(self.config_dir)
        if creds:
            self.username_input.setText(creds[0])
            self.password_input.setText(creds[1])
            # Hide login section if credentials exist
            self.login_group.hide()
            self.log("✓ Using saved credentials")

    def save_credentials(self):
        """Save credentials to file"""
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter username and password")
            return

        save_credentials(self.config_dir, username, password)
        self.log("✓ Credentials saved")

    def show_table_selector(self):
        """Show the table selector dialog"""
        all_tables = self.table_service.get_all_tables()
        if not all_tables:
            QMessageBox.warning(self, "Error", "No tables found in database")
            return

        dialog = TableSelectorDialog(all_tables, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_table:
            self.selected_table = dialog.selected_table
            self.selected_table_label.setText(self.selected_table.name)
            self.download_btn.setEnabled(True)
            self.log(f"Selected table: {self.selected_table.name}")

    def start_download(self):
        """Start the download process"""
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter FTP credentials")
            return

        if not self.selected_table:
            QMessageBox.warning(self, "Error", "Please select a table first")
            return

        # Clear previous downloads
        self.media_review.clear_files()

        # Start download thread
        self.download_thread = FTPDownloadThread(username, password, self.selected_table, self.config_dir)
        self.download_thread.progress.connect(self.update_status)
        self.download_thread.file_downloaded.connect(self.on_file_downloaded)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.start()

        # Update UI state
        self.download_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.select_table_btn.setEnabled(False)
        self.status_label.setText("Connecting to FTP server...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.progress_bar.show()
        self.log("Starting download...")

    def update_status(self, message: str):
        """Update the status label and log"""
        self.status_label.setText(message)
        self.log(message)

    def on_file_downloaded(self, media_type: str, temp_path: str, ftp_filename: str, table_name: str):
        """Handle file downloaded event"""
        self.media_review.add_file(media_type, temp_path, ftp_filename, table_name)
        self.status_label.setText(f"Downloaded: {ftp_filename}")

    def stop_download(self):
        """Stop the current download"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
            self.status_label.setText("✗ Download Stopped")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: orange;")
            self.log("Download stopped by user")
            self.download_finished(False, "Download stopped")

    def download_finished(self, success: bool, message: str):
        """Handle download completion"""
        self.download_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_table_btn.setEnabled(True)
        self.progress_bar.hide()

        if success:
            self.status_label.setText("✓ Download Complete")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: green;")
        else:
            if "stopped" not in message.lower():
                self.status_label.setText("✗ Download Failed")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: red;")

        self.log(message)

        if success:
            QMessageBox.information(self, "Download Complete", message)

    def log(self, message: str):
        """Add message to progress log"""
        self.progress_text.append(message)

    def scan_tables_on_startup(self):
        """Scan tables on startup"""
        self.run_table_scan()

    def scan_tables_on_exit(self):
        """Offer to scan tables before exit"""
        reply = QMessageBox.question(
            self,
            "Scan Tables",
            "Would you like to scan tables and update media links before exiting?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.run_table_scan()

    def run_table_scan(self):
        """Run the table scanner"""
        try:
            self.log("Starting table scan...")
            self.status_label.setText("Scanning tables...")

            # Create table scanner (no arguments needed)
            scanner = TableScanner()

            # Scan and get results
            results = scanner.scan_and_report()

            # Log summary
            if 'tables' in results:
                self.log(f"✓ Tables: {results['tables'].get('new', 0)} new, {results['tables'].get('updated', 0)} updated")
            if 'media' in results:
                self.log(f"✓ Media: {results['media'].get('updated', 0)} tables updated")

            self.log("✓ Table scan complete")
            self.status_label.setText("✓ Table scan complete")

            QMessageBox.information(self, "Scan Complete", "Table scan completed successfully!")

        except Exception as e:
            self.log(f"✗ Error scanning tables: {e}")
            self.status_label.setText("✗ Scan failed")
            QMessageBox.warning(self, "Scan Error", f"Error scanning tables:\n{e}")

    def closeEvent(self, event):
        """Handle window close event"""
        self.scan_tables_on_exit()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
