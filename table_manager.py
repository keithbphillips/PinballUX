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
import zipfile

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QSplitter, QTextEdit, QProgressBar, QMessageBox, QGroupBox, QDialog,
    QListWidget, QListWidgetItem, QDialogButtonBox, QSizePolicy, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPixmap, QMovie
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Handle both development and installed import paths
try:
    from pinballux.src.core.config import Config
    from pinballux.src.database.models import DatabaseManager
    from pinballux.src.database.service import TableService
    from pinballux.src.database.table_manager import TableManager as TableScanner
    from pinballux.src.media.manager import MediaManager
except ModuleNotFoundError:
    from src.core.config import Config
    from src.database.models import DatabaseManager
    from src.database.service import TableService
    from src.database.table_manager import TableManager as TableScanner
    from src.media.manager import MediaManager


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

    # Reject files with no actual title (only manufacturer/year in parentheses)
    # e.g., "(Bally 1978).mp3", "(Gottlieb 1992).mp3"
    if not filename_title or len(filename_title) < 3:
        return 0.0

    # Reject files that are just generic descriptions
    generic_terms = ['original', 'pinball', 'fx2', 'fx3', 'system']
    if filename_title.lower() in generic_terms:
        return 0.0

    # Calculate direct similarity
    direct_score = similarity_ratio(filename_title, table_title)

    # If direct match is good, return it
    if direct_score >= 0.90:
        return direct_score

    # Check if filename is a prefix/subset of table name (for variants like "Premium", "LE", etc.)
    # e.g., "Metallica" matches "Metallica Premium Monsters"
    if filename_title.lower() in table_title.lower():
        # Boost the score if it's a prefix match (filename starts the table name)
        if table_title.lower().startswith(filename_title.lower()):
            # Prefix match is very strong, but require minimum length
            # "Metallica" matching "Metallica Premium" - good
            # "A" matching "Attack from Mars" - too short
            if len(filename_title) >= 4:
                return 0.95  # High score for prefix matches with decent length
            else:
                return direct_score
        else:
            # Substring match (filename appears in middle/end of table name)
            # Less reliable, use direct score
            return direct_score

    return direct_score


def get_local_media_path(media_type: str, filename: str, config: Config = None) -> Path:
    """Get the local path for a media file based on type

    Args:
        media_type: Type of media (launch_audio, table_audio, backglass, table, dmd, topper, wheel)
        filename: Name of the media file
        config: Config object (if None, uses default project path)
    """
    # Use configured media directory or fall back to default
    if config and config.vpx.media_directory:
        base_path = Path(config.vpx.media_directory)
    else:
        base_path = Path("/opt/pinballux/data/media")

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


class FTPCacheScanThread(QThread):
    """Thread for scanning FTP directories and caching file listings"""
    progress = pyqtSignal(str)  # Status messages
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, username: str, password: str, db_manager: DatabaseManager):
        super().__init__()
        self.username = username
        self.password = password
        self.db_manager = db_manager

    def run(self):
        try:
            from pinballux.src.database.models import FTPMediaCache
        except ModuleNotFoundError:
            from src.database.models import FTPMediaCache
        from datetime import datetime

        try:
            # Connect to FTP
            self.progress.emit("Connecting to ftp.gameex.com...")
            ftp = FTP("ftp.gameex.com")
            ftp.encoding = 'latin-1'
            ftp.login(self.username, self.password)
            self.progress.emit("✓ Connected to FTP server")

            # Get media directories
            base_path = "/-PinballX-/Media/Visual Pinball"

            # Define media directories to scan
            media_mappings = {
                'launch_audio': [f"{base_path}/Table Audio"],
                'table_audio': [f"{base_path}/Table Audio"],
                'backglass': [
                    f"{base_path}/Backglass Images",
                    f"{base_path}/Backglass Videos"
                ],
                'table': [
                    f"{base_path}/Table Images",
                    f"{base_path}/Table Videos"
                ],
                'dmd': [
                    f"{base_path}/Real DMD Images",
                    f"{base_path}/Real DMD Color Videos"
                ],
                'topper': [
                    f"{base_path}/Topper Images",
                    f"{base_path}/Topper Videos"
                ],
                'wheel': [f"{base_path}/Wheel Images"]
            }

            # Clear existing cache
            self.progress.emit("Clearing old cache...")
            with self.db_manager.get_session() as session:
                session.query(FTPMediaCache).delete()
                session.commit()

            total_files = 0

            # Scan each media directory
            for media_type, directories in media_mappings.items():
                for directory in directories:
                    self.progress.emit(f"Scanning {media_type}: {directory}...")

                    try:
                        ftp.cwd(directory)

                        # Use NLST to get clean filenames (not full LIST details)
                        try:
                            filenames = []
                            ftp.retrlines('NLST', filenames.append)

                            # Filter media files
                            media_extensions = {
                                '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif',
                                '.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm',
                                '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'
                            }

                            with self.db_manager.get_session() as session:
                                for filename in filenames:
                                    ext = Path(filename).suffix.lower()
                                    if ext in media_extensions:
                                        cache_entry = FTPMediaCache(
                                            directory=directory,
                                            filename=filename,
                                            file_size=0,  # Size not critical for matching
                                            media_type=media_type
                                        )
                                        session.add(cache_entry)
                                        total_files += 1

                                session.commit()
                        except Exception as file_err:
                            self.progress.emit(f"⚠ Error parsing files in {directory}: {str(file_err)}")
                            continue

                        self.progress.emit(f"✓ Scanned {media_type}")

                    except Exception as e:
                        self.progress.emit(f"⚠ Could not scan {directory}: {str(e)}")
                        continue

            # Store last update time in settings
            try:
                from pinballux.src.database.models import Settings
            except ModuleNotFoundError:
                from src.database.models import Settings

            with self.db_manager.get_session() as session:
                try:
                    last_update = session.query(Settings).filter(Settings.key == 'ftp_cache_last_update').first()
                    if last_update:
                        last_update.value = datetime.utcnow().isoformat()
                        last_update.updated_at = datetime.utcnow()
                    else:
                        last_update = Settings(
                            key='ftp_cache_last_update',
                            value=datetime.utcnow().isoformat(),
                            type='string'
                        )
                        session.add(last_update)
                    session.commit()
                except Exception as e:
                    self.progress.emit(f"⚠ Could not update cache timestamp: {str(e)}")

            ftp.quit()
            self.finished.emit(True, f"✓ Cache updated! {total_files} files indexed.\n\nNow ready to Download Media.")

        except Exception as e:
            self.finished.emit(False, f"Error scanning FTP: {str(e)}")


class FTPDownloadThread(QThread):
    """Thread for FTP download operations"""
    progress = pyqtSignal(str)  # Status messages
    progress_update = pyqtSignal(int, int)  # current_file, total_files
    file_downloaded = pyqtSignal(str, str, str, str)  # media_type, temp_path, ftp_filename, table_name
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, username: str, password: str, table, config_dir: Path, db_manager: DatabaseManager, selected_categories: List[str] = None):
        super().__init__()
        self.username = username
        self.password = password
        self.table = table
        self.config_dir = config_dir
        self.db_manager = db_manager
        self.selected_categories = selected_categories if selected_categories else []
        # Use config directory for temp downloads (user-writable)
        self.temp_dir = Path(config_dir).parent / "ftp_downloads_temp"

    def run(self):
        try:
            from pinballux.src.database.models import FTPMediaCache
        except ModuleNotFoundError:
            from src.database.models import FTPMediaCache

        try:
            # Create temp directory
            self.temp_dir.mkdir(exist_ok=True)

            # Query cached database for matching files
            self.progress.emit("Searching cached media database...")
            matched_files = []

            # Extract table name for faster comparison
            table_name_base = self.table.name.split('(')[0].strip().lower()

            with self.db_manager.get_session() as session:
                # Get all cached files
                all_files = session.query(FTPMediaCache).all()
                total_files = len(all_files)

                self.progress.emit(f"Scanning {total_files} cached files...")

                # Match files to table
                checked = 0
                for cached_file in all_files:
                    checked += 1

                    # Progress update every 500 files
                    if checked % 500 == 0:
                        self.progress.emit(f"Checked {checked}/{total_files} files...")

                    # Quick pre-filter: Skip files that definitely won't match
                    # Extract filename base for comparison
                    file_base = Path(cached_file.filename).stem.split('(')[0].strip().lower()

                    # Skip if filename has no title or is too short
                    if len(file_base) < 3:
                        continue

                    # Skip if first 3 chars don't match at all (fast rejection)
                    if len(table_name_base) >= 3 and len(file_base) >= 3:
                        if file_base[:3] != table_name_base[:3]:
                            continue

                    # Skip if category not selected
                    if self.selected_categories and cached_file.media_type not in self.selected_categories:
                        continue

                    # Now do full similarity matching
                    score = match_file_to_table(cached_file.filename, self.table)

                    # Only download files with high similarity (90%+)
                    if score >= 0.90:
                        matched_files.append({
                            'filename': cached_file.filename,
                            'directory': cached_file.directory,
                            'media_type': cached_file.media_type,
                            'file_size': cached_file.file_size,
                            'score': score
                        })

            if not matched_files:
                self.finished.emit(True, "No matching media files found")
                return

            self.progress.emit(f"✓ Found {len(matched_files)} matching files")

            # Group files by directory for efficient batch downloading
            files_by_directory = {}
            for file_info in matched_files:
                directory = file_info['directory']
                if directory not in files_by_directory:
                    files_by_directory[directory] = []
                files_by_directory[directory].append(file_info)

            self.progress.emit(f"Organized into {len(files_by_directory)} directories")

            # Connect to FTP for downloading
            self.progress.emit("Connecting to ftp.gameex.com...")
            ftp = FTP("ftp.gameex.com")
            ftp.encoding = 'latin-1'
            ftp.login(self.username, self.password)
            self.progress.emit("✓ Connected to FTP")

            # Download matched files by directory
            download_count = 0
            total_to_download = len(matched_files)
            processed = 0

            for directory, files in files_by_directory.items():
                try:
                    # Change to directory once for all files in it
                    ftp.cwd(directory)
                    self.progress.emit(f"📁 In directory: {Path(directory).name}")

                    for file_info in files:
                        processed += 1
                        filename = file_info['filename']
                        media_type = file_info['media_type']

                        # Download to temp directory with media type structure
                        media_type_dir = self.temp_dir / media_type
                        media_type_dir.mkdir(exist_ok=True)

                        temp_path = media_type_dir / filename

                        if temp_path.exists():
                            # File already in cache, skip download but still add to list
                            self.progress_update.emit(processed, total_to_download)
                            self.progress.emit(f"⚡ [{processed}/{total_to_download}] Cached: {filename}")
                            self.file_downloaded.emit(media_type, str(temp_path), filename, self.table.name)
                        else:
                            # Download file
                            try:
                                import time
                                start_time = time.time()
                                bytes_downloaded = 0

                                def download_callback(data):
                                    nonlocal bytes_downloaded
                                    bytes_downloaded += len(data)
                                    f.write(data)

                                print(f"\n[DOWNLOAD] Starting: {filename}")
                                print(f"[DOWNLOAD] Directory: {directory}")

                                self.progress_update.emit(processed, total_to_download)
                                self.progress.emit(f"[{processed}/{total_to_download}] Downloading: {filename}")

                                with open(temp_path, 'wb') as f:
                                    ftp.retrbinary(f'RETR {filename}', download_callback)

                                elapsed = time.time() - start_time
                                speed_kbps = (bytes_downloaded / 1024) / elapsed if elapsed > 0 else 0
                                size_kb = bytes_downloaded / 1024

                                print(f"[DOWNLOAD] Complete: {filename}")
                                print(f"[DOWNLOAD] Size: {size_kb:.2f} KB, Time: {elapsed:.2f}s, Speed: {speed_kbps:.2f} KB/s")

                                download_count += 1
                                self.progress.emit(f"✓ [{processed}/{total_to_download}] Downloaded: {filename} ({size_kb:.1f} KB @ {speed_kbps:.1f} KB/s)")
                                self.file_downloaded.emit(media_type, str(temp_path), filename, self.table.name)
                            except Exception as e:
                                print(f"[DOWNLOAD] ERROR: {filename} - {str(e)}")
                                self.progress.emit(f"⚠ [{processed}/{total_to_download}] Failed: {filename} - {str(e)}")

                except Exception as dir_error:
                    self.progress.emit(f"⚠ Error accessing {directory}: {str(dir_error)}")
                    continue

            ftp.quit()
            self.progress.emit(f"✓ Complete: Downloaded {download_count}, Cached {processed - download_count}")
            self.finished.emit(True, f"Downloaded {download_count} new files, {processed - download_count} from cache")

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

    def __init__(self, config: Config = None, parent_window=None):
        super().__init__()
        self.config = config or Config()
        self.parent_window = parent_window  # Reference to MainWindow for accessing selected_table
        self.files: List[DownloadedFile] = []
        self.current_file: Optional[DownloadedFile] = None
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)  # Set volume to 100%
        self.media_player.setAudioOutput(self.audio_output)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        # Left panel - File tree
        left_panel = QVBoxLayout()

        # Buttons at top
        button_layout = QHBoxLayout()

        # Selection buttons
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(self.deselect_all_btn)

        # Save and delete buttons
        self.save_btn = QPushButton("Save Selected")
        self.save_btn.clicked.connect(self.save_selected)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.delete_all_btn = QPushButton("Delete All")
        self.delete_all_btn.clicked.connect(self.delete_all)
        button_layout.addWidget(self.delete_all_btn)

        left_panel.addLayout(button_layout)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["", "Downloaded Files"])  # Column 0 for checkbox, 1 for name
        self.file_tree.itemClicked.connect(self.on_file_clicked)
        self.file_tree.header().setStretchLastSection(True)
        self.file_tree.setColumnCount(2)
        self.file_tree.setColumnWidth(0, 30)  # Narrow column for checkbox
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
        self.existing_audio_output.setVolume(1.0)  # Set volume to 100%
        self.existing_media_player.setAudioOutput(self.existing_audio_output)
        self.existing_media_player.setVideoOutput(self.existing_video_widget)

        self.existing_preview_layout.addWidget(self.existing_image_label)
        self.existing_preview_layout.addWidget(self.existing_video_widget)

        right_panel.addWidget(self.existing_preview)

        # Fourth panel - Existing media tree for selected table
        fourth_panel = QVBoxLayout()

        existing_media_label = QLabel("Current Media for Selected Table")
        existing_media_label.setStyleSheet("font-weight: bold; padding: 5px;")
        fourth_panel.addWidget(existing_media_label)

        self.existing_media_tree = QTreeWidget()
        self.existing_media_tree.setHeaderLabel("Existing Files")
        self.existing_media_tree.itemClicked.connect(self.on_existing_media_clicked)
        fourth_panel.addWidget(self.existing_media_tree)

        # Add panels to splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(20)  # Add spacing between panels
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        middle_widget = QWidget()
        middle_widget.setLayout(middle_panel)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        fourth_widget = QWidget()
        fourth_widget.setLayout(fourth_panel)

        splitter.addWidget(left_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(right_widget)
        splitter.addWidget(fourth_widget)

        # Make panels resizable with initial sizes
        splitter.setStretchFactor(0, 1)  # Downloaded files
        splitter.setStretchFactor(1, 2)  # Downloaded preview
        splitter.setStretchFactor(2, 2)  # Existing preview
        splitter.setStretchFactor(3, 1)  # Existing media tree
        splitter.setSizes([300, 400, 400, 300])  # Initial sizes
        splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing

        layout.addWidget(splitter)
        self.setLayout(layout)

    def cleanup_media_players(self):
        """Properly cleanup media players to prevent resource leaks"""
        try:
            # Cleanup downloaded media player
            if self.media_player:
                self.media_player.stop()
                self.media_player.setSource(QUrl())
                self.media_player.setVideoOutput(None)
                self.media_player.setAudioOutput(None)

            # Cleanup existing media player
            if self.existing_media_player:
                self.existing_media_player.stop()
                self.existing_media_player.setSource(QUrl())
                self.existing_media_player.setVideoOutput(None)
                self.existing_media_player.setAudioOutput(None)
        except Exception as e:
            pass  # Ignore cleanup errors

    def add_file(self, media_type: str, temp_path: str, ftp_filename: str, table_name: str):
        """Add a downloaded file to the review list"""
        file = DownloadedFile(media_type, Path(temp_path), ftp_filename, table_name)
        self.files.append(file)
        self.update_file_tree()

    def clear_files(self):
        """Clear all files from the review list"""
        # Properly cleanup media players
        self.cleanup_media_players()

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

    def update_existing_media_tree(self):
        """Update the existing media tree for the selected table"""
        self.existing_media_tree.clear()

        if not self.parent_window or not self.parent_window.selected_table:
            return

        table = self.parent_window.selected_table

        # Define media categories and their corresponding table fields
        media_fields = {
            'Backglass': [
                ('backglass_image', '🖼️'),
                ('backglass_video', '🎬')
            ],
            'Table': [
                ('playfield_image', '🖼️'),
                ('table_video', '🎬')
            ],
            'DMD': [
                ('dmd_image', '🖼️'),
                ('dmd_video', '🎬')
            ],
            'Topper': [
                ('topper_image', '🖼️'),
                ('topper_video', '🎬')
            ],
            'Wheel': [
                ('wheel_image', '🖼️')
            ],
            'Audio': [
                ('launch_audio', '🔊 Launch'),
                ('table_audio', '🔊 Table')
            ]
        }

        # Populate tree
        for category, fields in media_fields.items():
            category_item = None
            has_media = False

            for field_name, icon in fields:
                media_path = getattr(table, field_name)
                if media_path:
                    # Create category item if not created yet
                    if not category_item:
                        category_item = QTreeWidgetItem(self.existing_media_tree, [category])
                        category_item.setExpanded(True)
                        has_media = True

                    # Add media file
                    filename = Path(media_path).name
                    file_item = QTreeWidgetItem(category_item, [f"{icon} {filename}"])
                    # Store the full path in UserRole for preview
                    file_item.setData(0, Qt.ItemDataRole.UserRole, media_path)

            # If no media in this category, show "None"
            if not has_media:
                category_item = QTreeWidgetItem(self.existing_media_tree, [category])
                category_item.setExpanded(False)
                QTreeWidgetItem(category_item, ["(none)"])

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
            type_item = QTreeWidgetItem(self.file_tree, ["", media_type.upper()])
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
                file_item = QTreeWidgetItem(type_item, ["", f"{status_icon} {type_icon} {file.ftp_filename}"])
                file_item.setData(1, Qt.ItemDataRole.UserRole, file)

                # Add checkbox for files that haven't been saved
                if file.status == "pending":
                    file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    file_item.setCheckState(0, Qt.CheckState.Unchecked)

        # Resize columns to fit content
        self.file_tree.resizeColumnToContents(0)
        self.file_tree.resizeColumnToContents(1)

        # Enable save button if there are files
        self.update_save_button_state()

        # Also update the existing media tree when files change
        self.update_existing_media_tree()

    def on_file_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle file click - for preview, not checkbox"""
        # Column 1 is the file name column (checkbox is column 0)
        file = item.data(1, Qt.ItemDataRole.UserRole)
        if not file:
            return

        self.current_file = file

        # Handle exclusive checkbox selection per media type
        if column == 0:  # Checkbox column clicked
            # If this file was just checked, uncheck all other files of the same media type
            if file and item.checkState(0) == Qt.CheckState.Checked:
                self.uncheck_other_files_in_media_type(item, file.media_type)

            self.update_save_button_state()

        # Stop and cleanup both media players completely
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.media_player.setVideoOutput(None)
        self.media_player.setAudioOutput(None)

        self.existing_media_player.stop()
        self.existing_media_player.setSource(QUrl())
        self.existing_media_player.setVideoOutput(None)
        self.existing_media_player.setAudioOutput(None)

        # Reset widget visibility to known state
        self.downloaded_video_widget.hide()
        self.downloaded_image_label.hide()
        self.existing_video_widget.hide()
        self.existing_image_label.hide()

        # Use QTimer to delay preview showing slightly to allow Qt to process the cleanup
        QTimer.singleShot(50, lambda: self._show_previews(file))

    def _show_previews(self, file: DownloadedFile):
        """Show previews after cleanup delay"""
        # Show downloaded file preview
        self.show_downloaded_preview(file)

        # Show existing file preview
        self.show_existing_preview(file)

        # Keep log scrolled to bottom to show newest entries
        main_window = self.window()
        if hasattr(main_window, 'progress_text'):
            cursor = main_window.progress_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            main_window.progress_text.setTextCursor(cursor)
            main_window.progress_text.ensureCursorVisible()

    def show_downloaded_preview(self, file: DownloadedFile):
        """Show preview of the downloaded file"""
        ext = file.temp_path.suffix.lower()

        # Remove both widgets from layout first
        self.downloaded_preview_layout.removeWidget(self.downloaded_image_label)
        self.downloaded_preview_layout.removeWidget(self.downloaded_video_widget)

        # ALWAYS destroy the old video widget first to clean up native overlay
        self.downloaded_video_widget.deleteLater()

        if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            # Video
            self.downloaded_image_label.hide()

            # Create a fresh video widget
            self.downloaded_video_widget = QVideoWidget()
            self.downloaded_video_widget.setMinimumSize(400, 300)
            self.downloaded_video_widget.mousePressEvent = lambda e: self.play_downloaded_media()

            # Add the new video widget to layout
            self.downloaded_preview_layout.addWidget(self.downloaded_video_widget)

            # Set video output and source
            self.media_player.setVideoOutput(self.downloaded_video_widget)
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.setSource(QUrl.fromLocalFile(str(file.temp_path)))

            # Show the widget
            self.downloaded_video_widget.show()

            # Force geometry update
            self.downloaded_video_widget.updateGeometry()
            QApplication.processEvents()

            # Start playback
            self.media_player.play()

        elif ext in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}:
            # Image
            # Create a new empty video widget (since we deleted the old one)
            self.downloaded_video_widget = QVideoWidget()
            self.downloaded_video_widget.setMinimumSize(400, 300)
            self.downloaded_video_widget.hide()

            self.downloaded_image_label.show()
            # Re-add image label to layout
            self.downloaded_preview_layout.addWidget(self.downloaded_image_label)
            self.downloaded_image_label.raise_()
            self.downloaded_image_label.setFocus()
            pixmap = QPixmap(str(file.temp_path))
            scaled_pixmap = pixmap.scaled(400, 400,
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            self.downloaded_image_label.setPixmap(scaled_pixmap)
            self.downloaded_image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        elif ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
            # Audio
            # Create a new empty video widget (since we deleted the old one)
            self.downloaded_video_widget = QVideoWidget()
            self.downloaded_video_widget.setMinimumSize(400, 300)
            self.downloaded_video_widget.hide()

            self.downloaded_image_label.show()
            # Re-add image label to layout
            self.downloaded_preview_layout.addWidget(self.downloaded_image_label)
            self.downloaded_image_label.raise_()
            self.downloaded_image_label.setFocus()
            self.downloaded_image_label.setText(f"🔊 Click to play: {file.ftp_filename}")
            self.media_player.setAudioOutput(self.audio_output)

    def find_existing_file(self, file: DownloadedFile) -> Optional[Path]:
        """Find existing file of the same media type, regardless of extension"""
        # Use configured media directory
        if self.config and self.config.vpx.media_directory:
            base_path = Path(self.config.vpx.media_directory)
        else:
            base_path = Path("/opt/pinballux/data/media")

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
                local_path = get_local_media_path(file.media_type, local_filename, self.config)
                if local_path.exists():
                    return local_path

        return None

    def on_existing_media_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle click on existing media tree to show preview"""
        # Get the stored file path
        media_path = item.data(0, Qt.ItemDataRole.UserRole)

        if not media_path:
            # Clicked on category or "(none)" - ignore
            return

        local_path = Path(media_path)
        if not local_path.exists():
            self.existing_image_label.setText(f"File not found:\n{local_path}")
            self.existing_image_label.setPixmap(QPixmap())
            self.existing_image_label.show()
            self.existing_video_widget.hide()
            return

        # Stop any playing media
        self.existing_media_player.stop()
        self.existing_media_player.setSource(QUrl())

        # Check file type and show appropriate preview
        ext = local_path.suffix.lower()

        if ext in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}:
            # Show image
            pixmap = QPixmap(str(local_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.existing_image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.existing_image_label.setPixmap(scaled_pixmap)
                self.existing_image_label.setText("")
            else:
                self.existing_image_label.setText(f"Failed to load image:\n{local_path.name}")
                self.existing_image_label.setPixmap(QPixmap())

            self.existing_image_label.show()
            self.existing_video_widget.hide()

        elif ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
            # Show video
            # Hide image label
            self.existing_image_label.hide()

            # Remove widgets from layout and destroy old video widget to clean up native overlay
            self.existing_preview_layout.removeWidget(self.existing_image_label)
            self.existing_preview_layout.removeWidget(self.existing_video_widget)
            self.existing_video_widget.deleteLater()

            # Create a fresh video widget
            self.existing_video_widget = QVideoWidget()
            self.existing_video_widget.setMinimumSize(400, 300)
            self.existing_video_widget.mousePressEvent = lambda e: self.play_existing_media()

            # Add the new video widget to layout
            self.existing_preview_layout.addWidget(self.existing_video_widget)

            # Set video output and source
            self.existing_media_player.setVideoOutput(self.existing_video_widget)
            self.existing_media_player.setSource(QUrl.fromLocalFile(str(local_path)))

            # Show the widget
            self.existing_video_widget.show()

            # Force geometry update
            self.existing_video_widget.updateGeometry()
            QApplication.processEvents()

            # Start playback
            self.existing_media_player.play()

        elif ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
            # Show audio indicator
            self.existing_image_label.setText(f"🔊 Click to play:\n{local_path.name}")
            self.existing_image_label.setPixmap(QPixmap())
            self.existing_image_label.show()
            self.existing_video_widget.hide()
            self.existing_image_label.setFocus()

            # Play audio
            self.existing_media_player.setAudioOutput(self.existing_audio_output)
            self.existing_media_player.setSource(QUrl.fromLocalFile(str(local_path)))
            self.existing_media_player.play()
        else:
            self.existing_image_label.setText(f"Cannot preview:\n{local_path.name}")
            self.existing_image_label.setPixmap(QPixmap())
            self.existing_image_label.show()
            self.existing_video_widget.hide()

    def show_existing_preview(self, file: DownloadedFile):
        """Show preview of the existing PinballUX file if it exists"""
        local_path = self.find_existing_file(file)

        # Remove both widgets from layout first
        self.existing_preview_layout.removeWidget(self.existing_image_label)
        self.existing_preview_layout.removeWidget(self.existing_video_widget)

        # ALWAYS destroy the old video widget first to clean up native overlay
        self.existing_video_widget.deleteLater()

        if local_path:
            ext = local_path.suffix.lower()

            if ext in {'.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm'}:
                # Video
                self.existing_image_label.hide()

                # Create a fresh video widget
                self.existing_video_widget = QVideoWidget()
                self.existing_video_widget.setMinimumSize(400, 300)
                self.existing_video_widget.mousePressEvent = lambda e: self.play_existing_media()

                # Add the new video widget to layout
                self.existing_preview_layout.addWidget(self.existing_video_widget)

                # Set video output and source
                self.existing_media_player.setVideoOutput(self.existing_video_widget)
                self.existing_media_player.setAudioOutput(self.existing_audio_output)
                self.existing_media_player.setSource(QUrl.fromLocalFile(str(local_path)))

                # Show the widget
                self.existing_video_widget.show()

                # Force geometry update
                self.existing_video_widget.updateGeometry()
                QApplication.processEvents()

                # Start playback
                self.existing_media_player.play()

            elif ext in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}:
                # Image
                # Create a new empty video widget (since we deleted the old one)
                self.existing_video_widget = QVideoWidget()
                self.existing_video_widget.setMinimumSize(400, 300)
                self.existing_video_widget.hide()

                self.existing_image_label.show()
                # Re-add image label to layout
                self.existing_preview_layout.addWidget(self.existing_image_label)
                self.existing_image_label.raise_()
                self.existing_image_label.setFocus()
                pixmap = QPixmap(str(local_path))
                scaled_pixmap = pixmap.scaled(400, 400,
                                              Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                self.existing_image_label.setPixmap(scaled_pixmap)
                self.existing_image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            elif ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                # Audio
                # Create a new empty video widget (since we deleted the old one)
                self.existing_video_widget = QVideoWidget()
                self.existing_video_widget.setMinimumSize(400, 300)
                self.existing_video_widget.hide()

                self.existing_image_label.show()
                # Re-add image label to layout
                self.existing_preview_layout.addWidget(self.existing_image_label)
                self.existing_image_label.raise_()
                self.existing_image_label.setFocus()
                self.existing_image_label.setText(f"🔊 Click to play existing: {local_path.name}")
                self.existing_media_player.setAudioOutput(self.existing_audio_output)
        else:
            # No existing file
            # Create a new empty video widget (since we deleted the old one)
            self.existing_video_widget = QVideoWidget()
            self.existing_video_widget.setMinimumSize(400, 300)
            self.existing_video_widget.hide()

            self.existing_image_label.show()
            # Re-add image label to layout
            self.existing_preview_layout.addWidget(self.existing_image_label)
            self.existing_image_label.raise_()
            self.existing_image_label.setText("No existing file")
            self.existing_image_label.setPixmap(QPixmap())

    def play_downloaded_media(self):
        """Play downloaded audio when clicked"""
        if self.current_file:
            ext = self.current_file.temp_path.suffix.lower()
            if ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                # Ensure audio output is connected
                self.media_player.setAudioOutput(self.audio_output)
                self.media_player.setSource(QUrl.fromLocalFile(str(self.current_file.temp_path)))
                self.media_player.play()

    def play_existing_media(self):
        """Play existing audio when clicked"""
        if self.current_file:
            local_path = self.find_existing_file(self.current_file)

            if local_path:
                ext = local_path.suffix.lower()
                if ext in {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}:
                    # Ensure audio output is connected
                    self.existing_media_player.setAudioOutput(self.existing_audio_output)
                    self.existing_media_player.setSource(QUrl.fromLocalFile(str(local_path)))
                    self.existing_media_player.play()

    def uncheck_other_files_in_media_type(self, checked_item: QTreeWidgetItem, media_type: str):
        """Uncheck all other files in the same media type category

        This ensures only ONE file per media type can be selected at a time.
        For example, if there are multiple table videos, only one should be checked.
        """
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()

            # Skip the item that was just checked
            if item == checked_item:
                iterator += 1
                continue

            file = item.data(1, Qt.ItemDataRole.UserRole)

            # If this file is the same media type and is checked, uncheck it
            if file and file.media_type == media_type and file.status == "pending":
                if item.checkState(0) == Qt.CheckState.Checked:
                    item.setCheckState(0, Qt.CheckState.Unchecked)

            iterator += 1

    def update_save_button_state(self):
        """Update save button enabled state based on selections"""
        has_checked = False
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            file = item.data(1, Qt.ItemDataRole.UserRole)
            if file and file.status == "pending":
                if item.checkState(0) == Qt.CheckState.Checked:
                    has_checked = True
                    break
            iterator += 1

        self.save_btn.setEnabled(has_checked)

    def select_all(self):
        """Select all pending files (last file in each media type will be selected due to exclusive logic)"""
        # Track which media types we've seen
        selected_per_type = {}

        # First pass: collect all items by media type
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            file = item.data(1, Qt.ItemDataRole.UserRole)
            if file and file.status == "pending":
                if file.media_type not in selected_per_type:
                    selected_per_type[file.media_type] = []
                selected_per_type[file.media_type].append(item)
            iterator += 1

        # Second pass: check the last item of each media type
        # (this simulates user clicking through all items, with last click winning)
        for media_type, items in selected_per_type.items():
            # Check the last item in each category
            if items:
                items[-1].setCheckState(0, Qt.CheckState.Checked)

        self.update_save_button_state()

    def deselect_all(self):
        """Deselect all files"""
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            file = item.data(1, Qt.ItemDataRole.UserRole)
            if file and file.status == "pending":
                item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1
        self.update_save_button_state()

    def save_selected(self):
        """Save all selected (checked) files"""
        # Collect checked files
        files_to_save = []
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            file = item.data(1, Qt.ItemDataRole.UserRole)
            if file and file.status == "pending" and item.checkState(0) == Qt.CheckState.Checked:
                files_to_save.append(file)
            iterator += 1

        if not files_to_save:
            QMessageBox.information(self, "No Selection", "Please select files to save using the checkboxes.")
            return

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Save Selected Files",
            f"Save {len(files_to_save)} selected file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Save each file
        saved_count = 0
        skipped_count = 0
        error_count = 0

        for file in files_to_save:
            try:
                # Generate local filename with table name
                local_filename = f"{file.table_name}{file.temp_path.suffix}"
                local_path = get_local_media_path(file.media_type, local_filename, self.config)

                # Check if any existing file exists (any extension of the same type)
                existing_file = self.find_existing_file(file)

                overwrite = True
                if existing_file and existing_file != local_path:
                    # File exists with different extension - ask once per file
                    reply = QMessageBox.question(
                        self,
                        "File Exists",
                        f"File already exists:\n{existing_file}\n\nWill be replaced with:\n{local_path}\n\nOverwrite?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                    )

                    if reply == QMessageBox.StandardButton.Cancel:
                        break  # Cancel entire operation
                    elif reply == QMessageBox.StandardButton.No:
                        overwrite = False

                if overwrite:
                    # Delete old file if different extension
                    if existing_file and existing_file != local_path and existing_file.exists():
                        existing_file.unlink()

                    # Create directory and copy file
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file.temp_path, local_path)

                    # Mark as saved
                    file.status = "saved"
                    saved_count += 1
                else:
                    file.status = "skipped"
                    skipped_count += 1

            except Exception as e:
                error_count += 1
                QMessageBox.warning(self, "Error", f"Failed to save {file.ftp_filename}:\n{str(e)}")

        # Update tree and show summary
        self.update_file_tree()

        # Update preview if current file was saved
        if self.current_file and self.current_file in files_to_save:
            self.show_existing_preview(self.current_file)

        # Update database with newly saved media files
        if saved_count > 0:
            self.parent_window.log(f"Updating database for {saved_count} saved media file(s)...")
            try:
                # Rescan media for all tables to pick up the newly saved files
                media_result = self.parent_window.table_service.rescan_all_media()
                self.parent_window.log(f"✓ Database updated: {media_result['updated']} tables with media changes")

                # Reload the selected table to refresh the existing media tree
                self.parent_window.reload_selected_table()
            except Exception as e:
                self.parent_window.log(f"⚠ Error updating database: {e}")

        # Show summary
        summary = f"Saved: {saved_count}"
        if skipped_count > 0:
            summary += f", Skipped: {skipped_count}"
        if error_count > 0:
            summary += f", Errors: {error_count}"

        QMessageBox.information(self, "Save Complete", summary)

    def save_current(self):
        """Save the current file to permanent location (legacy single-file save)"""
        if not self.current_file:
            return

        # Generate local filename with table name
        local_filename = f"{self.current_file.table_name}{self.current_file.temp_path.suffix}"
        local_path = get_local_media_path(self.current_file.media_type, local_filename, self.config)

        # Check if any existing file exists (any extension of the same type)
        existing_file = self.find_existing_file(self.current_file)

        if existing_file:
            # Only show confirmation if file will be overwritten
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

        # Update database with newly saved media file
        self.parent_window.log("Updating database for saved media file...")
        try:
            # Rescan media for all tables to pick up the newly saved file
            media_result = self.parent_window.table_service.rescan_all_media()
            self.parent_window.log(f"✓ Database updated: {media_result['updated']} tables with media changes")

            # Reload the selected table to refresh the existing media tree
            self.parent_window.reload_selected_table()
        except Exception as e:
            self.parent_window.log(f"⚠ Error updating database: {e}")

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

    def closeEvent(self, event):
        """Handle widget close event - cleanup media players"""
        self.cleanup_media_players()
        event.accept()


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.config_dir = Path(self.config.config_file).parent
        db_path = self.config_dir / "pinballux.db"
        self.db_manager = DatabaseManager(f"sqlite:///{db_path}")
        self.db_manager.initialize()

        # Initialize MediaManager for scanning media files
        self.media_manager = MediaManager(self.config)

        # Initialize TableService with MediaManager
        self.table_service = TableService(self.db_manager, self.media_manager)

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
        table_main_layout = QVBoxLayout()

        # Top row - table selection
        table_layout = QHBoxLayout()

        self.select_table_btn = QPushButton("Select Table...")
        self.select_table_btn.clicked.connect(self.show_table_selector)
        table_layout.addWidget(self.select_table_btn)

        self.selected_table_label = QLabel("No table selected")
        self.selected_table_label.setStyleSheet("font-weight: bold;")
        table_layout.addWidget(self.selected_table_label)

        table_layout.addStretch()
        table_main_layout.addLayout(table_layout)

        # Media category checkboxes
        media_group = QGroupBox("Media Categories to Download")
        media_checkboxes_layout = QHBoxLayout()

        self.media_category_checkboxes = {}
        media_categories = [
            ('backglass', 'Backglass'),
            ('table', 'Table'),
            ('dmd', 'DMD'),
            ('topper', 'Topper'),
            ('wheel', 'Wheel'),
            ('launch_audio', 'Launch Audio'),
            ('table_audio', 'Table Audio')
        ]

        for key, label in media_categories:
            checkbox = QPushButton(label)
            checkbox.setCheckable(True)
            checkbox.setChecked(True)  # Default to all checked
            checkbox.setStyleSheet("""
                QPushButton {
                    padding: 5px 10px;
                    border: 2px solid #555;
                    border-radius: 4px;
                    background-color: #4CAF50;
                    color: white;
                }
                QPushButton:checked {
                    background-color: #4CAF50;
                    border-color: #4CAF50;
                }
                QPushButton:!checked {
                    background-color: #999;
                    border-color: #666;
                }
            """)
            self.media_category_checkboxes[key] = checkbox
            media_checkboxes_layout.addWidget(checkbox)

        media_group.setLayout(media_checkboxes_layout)
        table_main_layout.addWidget(media_group)

        # Bottom row - action buttons
        button_layout = QHBoxLayout()

        self.download_btn = QPushButton("Download Media")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        button_layout.addWidget(self.download_btn)

        self.stop_btn = QPushButton("Stop Download")
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        self.import_pack_btn = QPushButton("Import Media Pack")
        self.import_pack_btn.clicked.connect(self.import_media_pack)
        self.import_pack_btn.setEnabled(False)
        button_layout.addWidget(self.import_pack_btn)

        self.import_csv_btn = QPushButton("Import CSV Database")
        self.import_csv_btn.clicked.connect(self.import_csv_database)
        self.import_csv_btn.setToolTip("Import table metadata (theme, IPDB number) from PinballX database CSV")
        button_layout.addWidget(self.import_csv_btn)

        self.refresh_cache_btn = QPushButton("Refresh Media Cache")
        self.refresh_cache_btn.clicked.connect(self.refresh_media_cache)
        self.refresh_cache_btn.setToolTip("Update the media file listing from FTP (recommended weekly)")
        button_layout.addWidget(self.refresh_cache_btn)

        table_main_layout.addLayout(button_layout)

        table_group.setLayout(table_main_layout)
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
        self.media_review = MediaReviewWidget(self.config, parent_window=self)
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

    def check_missing_media_categories(self, table) -> List[str]:
        """Check which media categories are missing for a table

        Args:
            table: Table object to check

        Returns:
            List of missing media category keys
        """
        missing_categories = []
        # Use configured media directory
        if self.config and self.config.vpx.media_directory:
            base_media_path = Path(self.config.vpx.media_directory)
        else:
            base_media_path = Path("/opt/pinballux/data/media")

        # Check backglass (images or videos)
        backglass_exists = False
        if table.backglass_image or table.backglass_video:
            backglass_exists = True
        else:
            # Check file system
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                img_path = base_media_path / "images" / "backglass" / f"{table.name}{ext}"
                vid_path = base_media_path / "videos" / "backglass" / f"{table.name}{ext}"
                if img_path.exists() or vid_path.exists():
                    backglass_exists = True
                    break
        if not backglass_exists:
            missing_categories.append('backglass')

        # Check table (images or videos)
        table_exists = False
        if table.table_video or table.playfield_image:
            table_exists = True
        else:
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                img_path = base_media_path / "images" / "table" / f"{table.name}{ext}"
                vid_path = base_media_path / "videos" / "table" / f"{table.name}{ext}"
                if img_path.exists() or vid_path.exists():
                    table_exists = True
                    break
        if not table_exists:
            missing_categories.append('table')

        # Check DMD (images or videos)
        dmd_exists = False
        if table.dmd_image or table.dmd_video:
            dmd_exists = True
        else:
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                for dmd_dir in ['images/dmd', 'images/real_dmd', 'videos/dmd', 'videos/fulldmd', 'videos/real_dmd', 'videos/real_dmd_color']:
                    dmd_path = base_media_path / dmd_dir / f"{table.name}{ext}"
                    if dmd_path.exists():
                        dmd_exists = True
                        break
                if dmd_exists:
                    break
        if not dmd_exists:
            missing_categories.append('dmd')

        # Check topper (images or videos)
        topper_exists = False
        if table.topper_image or table.topper_video:
            topper_exists = True
        else:
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.mp4', '.avi', '.f4v', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                img_path = base_media_path / "images" / "topper" / f"{table.name}{ext}"
                vid_path = base_media_path / "videos" / "topper" / f"{table.name}{ext}"
                if img_path.exists() or vid_path.exists():
                    topper_exists = True
                    break
        if not topper_exists:
            missing_categories.append('topper')

        # Check wheel
        wheel_exists = False
        if table.wheel_image:
            wheel_exists = True
        else:
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                wheel_path = base_media_path / "images" / "wheel" / f"{table.name}{ext}"
                if wheel_path.exists():
                    wheel_exists = True
                    break
        if not wheel_exists:
            missing_categories.append('wheel')

        # Check launch audio
        launch_audio_exists = False
        if table.launch_audio:
            launch_audio_exists = True
        else:
            for ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a']:
                audio_path = base_media_path / "audio" / "launch" / f"{table.name}{ext}"
                if audio_path.exists():
                    launch_audio_exists = True
                    break
        if not launch_audio_exists:
            missing_categories.append('launch_audio')

        # Check table audio
        table_audio_exists = False
        if table.table_audio:
            table_audio_exists = True
        else:
            for ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a']:
                audio_path = base_media_path / "audio" / "table" / f"{table.name}{ext}"
                if audio_path.exists():
                    table_audio_exists = True
                    break
        if not table_audio_exists:
            missing_categories.append('table_audio')

        return missing_categories

    def reload_selected_table(self):
        """Reload the selected table from database to get updated media paths"""
        if not self.selected_table:
            self.log("⚠ No table selected to reload")
            return

        table_id = self.selected_table.id
        table_name = self.selected_table.name

        # Reload table from database
        reloaded_table = self.table_service.get_table_by_id(table_id)
        if reloaded_table:
            self.selected_table = reloaded_table
            self.log(f"Reloaded table '{table_name}' (ID: {table_id}) from database")

            # Update the existing media tree to show newly saved files
            self.media_review.update_existing_media_tree()
            self.log("✓ Refreshed media view")
        else:
            self.log(f"⚠ Failed to reload table '{table_name}' (ID: {table_id})")

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
            self.import_pack_btn.setEnabled(True)
            self.log(f"Selected table: {self.selected_table.name}")

            # Update the existing media tree in the media review widget
            self.media_review.update_existing_media_tree()

            # Check which media categories are missing (for informational purposes only)
            missing_categories = self.check_missing_media_categories(self.selected_table)

            if missing_categories:
                self.log(f"Missing media categories: {', '.join(missing_categories)}")
            else:
                self.log("✓ All media categories exist for this table")

            # Note: User can manually select which categories to download using the checkboxes

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

        # Get selected media categories
        selected_categories = [
            key for key, checkbox in self.media_category_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_categories:
            QMessageBox.warning(self, "Error", "Please select at least one media category")
            return

        # Check if media cache needs refresh
        # If a cache refresh is triggered, abort this download
        if self.check_cache_age():
            self.log("Please click Download Media again after cache refresh completes")
            return

        # Clear previous downloads
        self.media_review.clear_files()

        # Start download thread with selected categories
        self.download_thread = FTPDownloadThread(username, password, self.selected_table, self.config_dir, self.db_manager, selected_categories)
        self.download_thread.progress.connect(self.update_status)
        self.download_thread.progress_update.connect(self.update_progress_bar)
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
        self.log(f"Starting download for categories: {', '.join(selected_categories)}...")

    def update_status(self, message: str):
        """Update the status label and log"""
        self.status_label.setText(message)
        self.log(message)

    def on_file_downloaded(self, media_type: str, temp_path: str, ftp_filename: str, table_name: str):
        """Handle file downloaded event"""
        self.media_review.add_file(media_type, temp_path, ftp_filename, table_name)

    def update_progress_bar(self, current: int, total: int):
        """Update progress bar with current progress"""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)

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
        self.progress_bar.setRange(0, 0)  # Reset to indeterminate for next time
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

    def check_cache_age(self):
        """Check if media cache needs refresh (weekly)

        Returns:
            True if cache refresh was triggered, False otherwise
        """
        try:
            from pinballux.src.database.models import Settings
        except ModuleNotFoundError:
            from src.database.models import Settings
        from datetime import datetime, timedelta

        try:
            with self.db_manager.get_session() as session:
                last_update = session.query(Settings).filter(Settings.key == 'ftp_cache_last_update').first()

                if not last_update:
                    # No cache exists, must create one
                    QMessageBox.information(
                        self,
                        "Media Cache Required",
                        "No media cache found. Building cache now...\n\n"
                        "This will scan FTP media directories (takes 1-2 minutes) and enables fast media searches."
                    )

                    # Trigger refresh after credentials are loaded
                    QTimer.singleShot(500, self.auto_refresh_cache)
                    return True

                # Check if cache is older than 7 days
                last_update_time = datetime.fromisoformat(last_update.value)
                age = datetime.utcnow() - last_update_time

                if age > timedelta(days=7):
                    days_old = age.days
                    reply = QMessageBox.question(
                        self,
                        "Media Cache Update",
                        f"Media cache is {days_old} days old. Would you like to refresh it?\n\n"
                        "Recommended: Update weekly for latest media files.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )

                    if reply == QMessageBox.StandardButton.Yes:
                        QTimer.singleShot(500, self.auto_refresh_cache)
                        return True

        except Exception as e:
            self.log(f"Error checking cache age: {e}")

        return False

    def auto_refresh_cache(self):
        """Auto-refresh cache (called from timer)"""
        if self.username_input.text() and self.password_input.text():
            self.refresh_media_cache(skip_confirmation=True)
        else:
            QMessageBox.information(
                self,
                "FTP Credentials Required",
                "Please enter FTP credentials and click 'Refresh Media Cache' to update the cache."
            )

    def scan_tables_on_startup(self):
        """Scan tables on startup and validate media paths"""
        # First, validate media paths to ensure database is in sync with filesystem
        self.log("Validating media paths...")
        try:
            validation_result = self.table_service.validate_and_update_media_paths()
            if validation_result['missing'] > 0:
                self.log(f"⚠ Cleared {validation_result['missing']} missing media files from {validation_result['cleared']} tables")
            else:
                self.log("✓ All media paths validated")
        except Exception as e:
            self.log(f"⚠ Error validating media paths: {e}")

        # Then run the normal table scan
        self.run_table_scan()

    def scan_tables_on_exit(self):
        """No longer needed - database is updated automatically when media files are saved"""
        # Database is kept in sync automatically:
        # - Media paths are validated on startup
        # - Database is updated immediately when media files are saved
        pass

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

        except Exception as e:
            self.log(f"✗ Error scanning tables: {e}")
            self.status_label.setText("✗ Scan failed")
            QMessageBox.warning(self, "Scan Error", f"Error scanning tables:\n{e}")

    def refresh_media_cache(self, skip_confirmation=False):
        """Refresh the FTP media cache"""
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter FTP credentials")
            return

        if not skip_confirmation:
            reply = QMessageBox.question(
                self,
                "Refresh Media Cache",
                "This will scan all FTP media directories and update the cache.\n\nThis may take 1-2 minutes. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        # Start cache scan thread
        self.cache_scan_thread = FTPCacheScanThread(username, password, self.db_manager)
        self.cache_scan_thread.progress.connect(self.update_status)
        self.cache_scan_thread.finished.connect(self.cache_refresh_finished)
        self.cache_scan_thread.start()

        # Update UI state
        self.refresh_cache_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.select_table_btn.setEnabled(False)
        self.status_label.setText("Refreshing media cache...")
        self.progress_bar.show()
        self.log("Starting cache refresh...")

    def cache_refresh_finished(self, success: bool, message: str):
        """Handle cache refresh completion"""
        self.refresh_cache_btn.setEnabled(True)
        self.download_btn.setEnabled(bool(self.selected_table))
        self.select_table_btn.setEnabled(True)
        self.progress_bar.hide()

        if success:
            self.status_label.setText("✓ Cache Refreshed")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: green;")
        else:
            self.status_label.setText("✗ Cache Refresh Failed")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: red;")

        self.log(message)
        QMessageBox.information(self, "Cache Refresh", message)

    def import_media_pack(self):
        """Import a media pack from a zip file"""
        if not self.selected_table:
            QMessageBox.warning(self, "Error", "Please select a table first")
            return

        # Default to the media packs directory (use configured media dir)
        if self.config and self.config.vpx.media_directory:
            base_media_path = Path(self.config.vpx.media_directory)
        else:
            base_media_path = Path("/opt/pinballux/data/media")

        packs_dir = base_media_path / "packs"
        packs_dir.mkdir(parents=True, exist_ok=True)

        # Open file dialog to select zip file
        zip_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media Pack",
            str(packs_dir),
            "Zip Files (*.zip)"
        )

        if not zip_path:
            return  # User cancelled

        try:
            self.log(f"Importing media pack: {Path(zip_path).name}")
            self.status_label.setText("Importing media pack...")

            # Map HyperPin/PinballX media directories to PinballUX media types
            media_dir_mapping = {
                'Backglass Images': ('backglass', 'images'),
                'Backglass Videos': ('backglass', 'videos'),
                'Table Images': ('table', 'images'),
                'Table Videos': ('table', 'videos'),
                'table video': ('table', 'videos'),
                'Wheel Images': ('wheel', 'images'),
                'DMD Images': ('dmd', 'images'),
                'DMD Videos': ('dmd', 'videos'),
                'DMD Color Videos': ('dmd', 'videos'),
                'FullDMD Videos': ('dmd', 'videos'),
                'Real DMD Images': ('dmd', 'images'),
                'Real DMD Videos': ('dmd', 'videos'),
                'Real DMD Color Images': ('dmd', 'images'),
                'Real DMD Color Videos': ('dmd', 'videos'),
                'Topper Images': ('topper', 'images'),
                'Topper Videos': ('topper', 'videos'),
                'Launch Audio': ('launch_audio', 'audio'),
                'Table Audio': ('table_audio', 'audio'),
            }

            imported_files = []
            # base_media_path already set above from config

            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                for file_info in zip_file.filelist:
                    # Skip directories
                    if file_info.is_dir():
                        continue

                    # Parse the path to find media type
                    parts = Path(file_info.filename).parts

                    # Find media directory in path (e.g., "Backglass Images", "Table Videos")
                    media_dir = None
                    for part in parts:
                        if part in media_dir_mapping:
                            media_dir = part
                            break

                    if not media_dir:
                        continue  # Skip files not in known media directories

                    media_type, file_category = media_dir_mapping[media_dir]

                    # Extract filename
                    filename = Path(file_info.filename).name

                    # Rename file to use the selected table name
                    ext = Path(filename).suffix
                    new_filename = f"{self.selected_table.name}{ext}"

                    # Determine destination path based on media type and category
                    if media_type == 'launch_audio':
                        dest_path = base_media_path / "audio" / "launch" / new_filename
                    elif media_type == 'table_audio':
                        dest_path = base_media_path / "audio" / "table" / new_filename
                    elif media_type == 'backglass':
                        dest_path = base_media_path / file_category / "backglass" / new_filename
                    elif media_type == 'table':
                        dest_path = base_media_path / file_category / "table" / new_filename
                    elif media_type == 'dmd':
                        # For DMD videos, use real_dmd_color subdirectory
                        if file_category == 'videos':
                            dest_path = base_media_path / "videos" / "real_dmd_color" / new_filename
                        else:
                            dest_path = base_media_path / "images" / "dmd" / new_filename
                    elif media_type == 'topper':
                        dest_path = base_media_path / file_category / "topper" / new_filename
                    elif media_type == 'wheel':
                        dest_path = base_media_path / "images" / "wheel" / new_filename
                    else:
                        continue

                    # Create directory if needed
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # Check if file exists and ask for confirmation
                    if dest_path.exists():
                        reply = QMessageBox.question(
                            self,
                            "File Exists",
                            f"File already exists:\n{dest_path}\n\nOverwrite?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                        )

                        if reply == QMessageBox.StandardButton.Cancel:
                            self.log("Import cancelled by user")
                            return
                        elif reply == QMessageBox.StandardButton.No:
                            continue  # Skip this file

                    # Extract and save the file
                    with zip_file.open(file_info.filename) as source:
                        with open(dest_path, 'wb') as target:
                            shutil.copyfileobj(source, target)

                    imported_files.append((media_type, dest_path))
                    self.log(f"✓ Imported: [{media_type}] {dest_path.name}")

            # Show summary
            if imported_files:
                self.status_label.setText(f"✓ Imported {len(imported_files)} files")
                self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: green;")

                summary = f"Successfully imported {len(imported_files)} files:\n\n"
                media_counts = {}
                for media_type, _ in imported_files:
                    media_counts[media_type] = media_counts.get(media_type, 0) + 1

                for media_type, count in sorted(media_counts.items()):
                    summary += f"  • {media_type}: {count} file(s)\n"

                QMessageBox.information(self, "Import Complete", summary)
                self.log(f"✓ Media pack import complete: {len(imported_files)} files")
            else:
                self.status_label.setText("No matching media files found in pack")
                QMessageBox.warning(self, "Import Complete", "No matching media files found in the selected pack")

        except Exception as e:
            self.log(f"✗ Error importing media pack: {e}")
            self.status_label.setText("✗ Import failed")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: red;")
            QMessageBox.critical(self, "Import Error", f"Error importing media pack:\n{e}")

    def import_csv_database(self):
        """Import table metadata from PinballX database CSV file"""
        # Check if CSV file exists in project root first
        default_csv_path = Path(project_root) / "pinballxdatabase.csv"

        if default_csv_path.exists():
            csv_path = str(default_csv_path)
            self.log(f"Found CSV file: {default_csv_path.name}")
        else:
            # Fall back to file dialog if not found
            csv_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select PinballX Database CSV",
                str(Path.home()),
                "CSV Files (*.csv);;All Files (*.*)"
            )

            if not csv_path:
                return  # User cancelled

        try:
            # Import parser
            try:
                from pinballux.src.database.pinballx_database_parser import PinballXDatabaseParser
            except ModuleNotFoundError:
                from src.database.pinballx_database_parser import PinballXDatabaseParser

            self.log(f"Parsing CSV file: {Path(csv_path).name}")
            self.status_label.setText("Parsing CSV database...")

            # Parse CSV file
            parser = PinballXDatabaseParser(csv_path)
            csv_data = parser.parse()

            if not csv_data:
                QMessageBox.warning(self, "Import Error", "No data found in CSV file")
                return

            self.log(f"✓ Parsed {len(csv_data)} tables from CSV")

            # Match CSV data to existing tables and update
            matched_count = 0
            updated_count = 0
            all_tables = self.table_service.get_all_tables(enabled_only=False)

            self.log(f"Matching {len(all_tables)} tables in database...")
            self.status_label.setText(f"Matching {len(all_tables)} tables...")

            for table in all_tables:
                # Try to find matching CSV entry
                csv_entry = parser.find_table_by_name(
                    table.name,
                    table.manufacturer,
                    table.year
                )

                if csv_entry:
                    matched_count += 1

                    # Check if we need to update anything
                    needs_update = False
                    update_fields = []

                    if csv_entry.get('theme') and csv_entry['theme'] != table.theme:
                        table.theme = csv_entry['theme']
                        needs_update = True
                        update_fields.append('theme')

                    if csv_entry.get('ipdb_number') and csv_entry['ipdb_number'] != table.ipdb_number:
                        table.ipdb_number = csv_entry['ipdb_number']
                        needs_update = True
                        update_fields.append('IPDB')

                    # Update author if not set
                    if csv_entry.get('author') and not table.author:
                        table.author = csv_entry['author']
                        needs_update = True
                        update_fields.append('author')

                    # Update players if not set
                    if csv_entry.get('players') and csv_entry['players'] != table.players:
                        table.players = csv_entry['players']
                        needs_update = True
                        update_fields.append('players')

                    if needs_update:
                        updated_count += 1
                        self.log(f"  ✓ Updated {table.name}: {', '.join(update_fields)}")

            # Save changes
            with self.db_manager.get_session() as session:
                for table in all_tables:
                    session.merge(table)
                session.commit()

            # Show summary
            self.status_label.setText("✓ CSV import complete")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: green;")

            summary = (
                f"CSV Import Complete!\n\n"
                f"Total CSV entries: {len(csv_data)}\n"
                f"Matched tables: {matched_count}\n"
                f"Updated tables: {updated_count}\n\n"
                f"Table metadata (theme, IPDB number, author, players) has been imported."
            )

            self.log(f"✓ Import complete: {matched_count} matched, {updated_count} updated")
            QMessageBox.information(self, "Import Complete", summary)

        except Exception as e:
            self.log(f"✗ Error importing CSV: {e}")
            self.status_label.setText("✗ CSV import failed")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: red;")
            QMessageBox.critical(self, "Import Error", f"Error importing CSV:\n{e}")

    def closeEvent(self, event):
        """Handle window close event"""
        # Cleanup media players first
        if hasattr(self, 'media_review'):
            self.media_review.cleanup_media_players()

        self.scan_tables_on_exit()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
