"""
Main window for table selection interface
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QScrollArea, QPushButton, QLineEdit,
                             QComboBox, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor

from ..core.config import Config
from ..core.logger import get_logger
from ..displays.monitor_manager import MonitorManager
from .media_widgets import TableMediaWidget, AttractModeWidget, AudioPlayer


class TableWidget(QFrame):
    """Widget representing a single table in the grid"""

    clicked = pyqtSignal(dict)  # table_data

    def __init__(self, table_data: dict):
        super().__init__()
        self.table_data = table_data
        self.is_selected = False

        self._setup_ui()

    def _setup_ui(self):
        """Set up the table widget UI"""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setFixedSize(200, 300)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Table media widget (image/video)
        self.media_widget = TableMediaWidget()
        self.media_widget.setFixedSize(190, 200)

        # Load table media if available
        image_path = self.table_data.get('image', '')
        video_path = self.table_data.get('video', '')

        # Prefer video over image for thumbnails
        if video_path:
            self.media_widget.load_media(video_path)
        elif image_path:
            self.media_widget.load_media(image_path)

        layout.addWidget(self.media_widget)

        # Table name
        self.name_label = QLabel(self.table_data.get('name', 'Unknown Table'))
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: white;")
        layout.addWidget(self.name_label)

        # Manufacturer and year
        manufacturer = self.table_data.get('manufacturer', '')
        year = self.table_data.get('year', '')
        info_text = f"{manufacturer} ({year})" if manufacturer and year else manufacturer or year or ''

        self.info_label = QLabel(info_text)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-size: 12px; color: #ccc;")
        layout.addWidget(self.info_label)

        self._update_style()

    def _update_style(self):
        """Update widget style based on selection state"""
        if self.is_selected:
            self.setStyleSheet("""
                TableWidget {
                    background-color: #2a2a2a;
                    border: 2px solid #555;
                    border-radius: 5px;
                }
            """)
        else:
            self.setStyleSheet("""
                TableWidget {
                    background-color: #2a2a2a;
                    border: 2px solid #555;
                    border-radius: 5px;
                }
                TableWidget:hover {
                    background-color: #3a3a3a;
                    border: 2px solid #777;
                }
            """)

    def set_selected(self, selected: bool):
        """Set selection state"""
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.table_data)
        super().mousePressEvent(event)


class MainWindow(QWidget):
    """Main table selection window"""

    # Signals
    table_selected = pyqtSignal(str)  # table file path
    exit_requested = pyqtSignal()

    def __init__(self, config: Config, monitor_manager: MonitorManager, table_service=None, launch_manager=None):
        super().__init__()
        self.config = config
        self.monitor_manager = monitor_manager
        self.table_service = table_service
        self.launch_manager = launch_manager
        self.logger = get_logger(__name__)

        # Current state
        self.current_selected_table = None
        self.table_widgets = []
        self.filtered_tables = []
        self.all_tables = []

        # Audio player for launch sounds
        self.audio_player = AudioPlayer(self)

        self._setup_ui()
        self._populate_tables()

        # Attract mode timer
        self.attract_timer = QTimer()
        self.attract_timer.timeout.connect(self._update_attract_mode)
        self.attract_timer.start(30000)  # 30 seconds

    def _setup_ui(self):
        """Set up the main window UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("PinballUX - Select a Table")
        title_label.setStyleSheet("font-size: 32px; font-weight: bold; color: white;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Search and filter controls
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search tables...")
        self.search_edit.setFixedWidth(200)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 14px;
                background-color: #444;
                border: 2px solid #666;
                border-radius: 5px;
                color: white;
            }
            QLineEdit:focus {
                border: 2px solid #0088ff;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_tables)
        header_layout.addWidget(self.search_edit)

        # Manufacturer filter
        self.manufacturer_combo = QComboBox()
        self.manufacturer_combo.addItem("All Manufacturers")
        self.manufacturer_combo.setFixedWidth(150)
        self.manufacturer_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                font-size: 14px;
                background-color: #444;
                border: 2px solid #666;
                border-radius: 5px;
                color: white;
            }
        """)
        self.manufacturer_combo.currentTextChanged.connect(self._filter_tables)
        header_layout.addWidget(self.manufacturer_combo)

        layout.addLayout(header_layout)

        # Table grid area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a1a;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #333;
                width: 15px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background-color: #666;
                border-radius: 7px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #888;
            }
        """)

        # Grid widget
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.grid_widget)
        layout.addWidget(self.scroll_area)

        # Status bar
        status_layout = QHBoxLayout()

        self.status_label = QLabel("Ready - Select a table to play")
        self.status_label.setStyleSheet("font-size: 16px; color: #ccc;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # Table count
        self.count_label = QLabel("0 tables")
        self.count_label.setStyleSheet("font-size: 14px; color: #999;")
        status_layout.addWidget(self.count_label)

        layout.addLayout(status_layout)

        # Set window style
        self.setStyleSheet("background-color: #1a1a1a;")

    def _populate_tables(self):
        """Populate the table grid with available tables"""
        # Clear existing widgets
        for widget in self.table_widgets:
            widget.setParent(None)
        self.table_widgets.clear()

        # Load tables from database
        if self.table_service:
            self.all_tables = self.table_service.get_all_tables()
            self.logger.info(f"Loaded {len(self.all_tables)} tables from database")
        else:
            self.all_tables = []
            self.logger.warning("No table service available, showing empty table list")

        # Add manufacturer filter options
        manufacturers = set()
        for table in self.all_tables:
            if table.manufacturer:
                manufacturers.add(table.manufacturer)

        self.manufacturer_combo.clear()
        self.manufacturer_combo.addItem("All Manufacturers")
        for manufacturer in sorted(manufacturers):
            self.manufacturer_combo.addItem(manufacturer)

        # Create table widgets
        self.filtered_tables = self.all_tables.copy()
        self._update_grid()

    def _update_grid(self):
        """Update the table grid layout"""
        # Clear grid
        for widget in self.table_widgets:
            widget.setParent(None)
        self.table_widgets.clear()

        # Calculate grid dimensions
        columns = max(1, (self.scroll_area.width() - 50) // 220)  # 200px + 20px spacing

        # Add filtered tables to grid
        for i, table in enumerate(self.filtered_tables):
            # Convert Table model to dict for TableWidget
            table_data = {
                'id': table.id,
                'name': table.name,
                'manufacturer': table.manufacturer or '',
                'year': table.year or '',
                'file': table.file_path,
                'image': table.playfield_image or '',
                'video': table.table_video or '',
                'backglass_image': table.backglass_image or '',
                'dmd_image': table.dmd_image or '',
                'topper_image': table.topper_image or '',
                'launch_audio': table.launch_audio or '',
                'rating': table.rating or 0,
                'description': table.description or '',
                'play_count': table.play_count,
                'last_played': table.last_played,
                'favorite': table.favorite
            }
            widget = TableWidget(table_data)
            widget.clicked.connect(self._on_table_selected)

            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(widget, row, col)
            self.table_widgets.append(widget)

        # Update count
        self.count_label.setText(f"{len(self.filtered_tables)} tables")

    def _filter_tables(self):
        """Filter tables based on search and filter criteria"""
        search_text = self.search_edit.text().lower()
        selected_manufacturer = self.manufacturer_combo.currentText()

        self.filtered_tables = []

        for table in self.all_tables:
            # Search filter
            if search_text:
                table_text = f"{table.name} {table.manufacturer or ''} {table.year or ''} {table.description or ''}".lower()
                if search_text not in table_text:
                    continue

            # Manufacturer filter
            if selected_manufacturer != "All Manufacturers":
                if table.manufacturer != selected_manufacturer:
                    continue

            self.filtered_tables.append(table)

        self._update_grid()

    def _on_table_selected(self, table_data: dict):
        """Handle table selection"""
        # Update selection state
        for widget in self.table_widgets:
            widget.set_selected(widget.table_data == table_data)

        self.current_selected_table = table_data
        self.status_label.setText(f"Selected: {table_data.get('name', 'Unknown Table')}")

        # Update displays with table info
        if self.monitor_manager:
            # Update backglass
            self.monitor_manager.update_display_content("backglass", {
                'table_name': table_data.get('name', 'Unknown Table'),
                'manufacturer': table_data.get('manufacturer', ''),
                'year': table_data.get('year', ''),
                'backglass_image': table_data.get('backglass_image', '')
            })

            # Update DMD with image if available, otherwise show message
            dmd_image = table_data.get('dmd_image', '')
            if dmd_image:
                self.monitor_manager.update_display_content("dmd", {
                    'dmd_image': dmd_image,
                    'animation': False
                })
            else:
                self.monitor_manager.update_display_content("dmd", {
                    'message': f"SELECTED: {table_data.get('name', 'UNKNOWN')[:12].upper()}",
                    'animation': True
                })

            # Update topper
            self.monitor_manager.update_display_content("topper", {
                'table_name': table_data.get('name', 'Unknown Table'),
                'effect': 'table_selected'
            })

        self.logger.info(f"Table selected: {table_data.get('name')}")

    def _update_attract_mode(self):
        """Update attract mode displays"""
        if not self.current_selected_table:
            # Show attract mode on displays
            if self.monitor_manager:
                # Cycle through different attract messages
                import random
                attract_messages = [
                    "PRESS START TO PLAY",
                    "SELECT A TABLE",
                    "PINBALLUX READY",
                    "CHOOSE YOUR GAME"
                ]

                message = random.choice(attract_messages)

                self.monitor_manager.update_display_content("dmd", {
                    'message': message,
                    'animation': True
                })

                self.monitor_manager.update_display_content("topper", {
                    'effect': 'attract'
                })

    def keyPressEvent(self, event):
        """Handle key press events"""
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.exit_requested.emit()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            if self.current_selected_table:
                # Launch selected table
                self._launch_selected_table()
        elif key == Qt.Key.Key_F5:
            # Refresh table list
            self._populate_tables()

        super().keyPressEvent(event)

    def _launch_selected_table(self):
        """Launch the currently selected table"""
        if not self.current_selected_table or not self.launch_manager:
            return

        table_id = self.current_selected_table.get('id')
        if table_id:
            self.logger.info(f"Launching table: {self.current_selected_table.get('name')}")

            # Play launch audio if available
            launch_audio = self.current_selected_table.get('launch_audio', '')
            if launch_audio:
                self.audio_player.play_once(launch_audio)
                self.logger.info(f"Playing launch audio: {launch_audio}")

            # Update displays to show launching state
            if self.monitor_manager:
                self.monitor_manager.update_display_content("dmd", {
                    'message': "LAUNCHING...",
                    'animation': True
                })
                self.monitor_manager.update_display_content("topper", {
                    'table_name': self.current_selected_table.get('name'),
                    'effect': 'launching'
                })

            # Launch the table
            success = self.launch_manager.launch_table_by_id(table_id)
            if not success:
                self.logger.error("Failed to launch table")
                # Update displays to show error
                if self.monitor_manager:
                    self.monitor_manager.update_display_content("dmd", {
                        'message': "LAUNCH FAILED",
                        'animation': False
                    })

    def resizeEvent(self, event):
        """Handle window resize"""
        super().resizeEvent(event)
        # Recalculate grid when window is resized
        QTimer.singleShot(100, self._update_grid)  # Slight delay to avoid rapid updates