#!/usr/bin/env python3
"""
Debug wheel movement issue
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

# Add the pinballux directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from pinballux.src.ui.wheel_widget import WheelWidget

class DebugWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Debug Wheel Movement")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel("Press Left/Right arrows to test wheel movement")
        self.status_label.setStyleSheet("color: white; font-size: 16px; padding: 10px;")
        layout.addWidget(self.status_label)

        # Create wheel widget
        self.wheel_widget = WheelWidget()
        layout.addWidget(self.wheel_widget)

        # Create test tables
        test_tables = []
        for i in range(10):
            test_tables.append({
                'id': i,
                'name': f'Test Table {i+1}',
                'manufacturer': 'Test Manufacturer',
                'year': '2024',
                'file_path': f'/fake/path/table{i}.vpx',
                'wheel_image': '',
                'table_video': '',
                'backglass_image': '',
                'play_count': 0,
                'rating': 0,
                'description': f'Test table number {i+1}'
            })

        self.wheel_widget.set_tables(test_tables)

        # Set focus to wheel widget
        self.wheel_widget.setFocus()

        # Set dark background
        self.setStyleSheet("background-color: #1a1a1a;")

    def keyPressEvent(self, event):
        """Debug key press events"""
        key = event.key()

        if key == Qt.Key.Key_Left:
            self.status_label.setText("LEFT key pressed - calling move_wheel_left()")
            print("DEBUG: LEFT key pressed")
            self.wheel_widget.move_wheel_left()
        elif key == Qt.Key.Key_Right:
            self.status_label.setText("RIGHT key pressed - calling move_wheel_right()")
            print("DEBUG: RIGHT key pressed")
            self.wheel_widget.move_wheel_right()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.status_label.setText("ENTER key pressed - selecting table")
            print("DEBUG: ENTER key pressed")
            self.wheel_widget.select_current_table()
        elif key == Qt.Key.Key_Escape:
            self.close()
        else:
            print(f"DEBUG: Other key pressed: {key}")
            super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv)

    window = DebugWindow()
    window.show()

    print("Debug window shown. Use Left/Right arrows to test wheel movement.")
    print("Current index should change and wheel should animate.")
    print("Press ESC to exit.")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()