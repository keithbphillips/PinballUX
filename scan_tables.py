#!/usr/bin/env python3
"""
PinballUX - Table Scanner
Scans for VPX tables and media files, updates database
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import and run the table scanner
from pinballux.src.database.table_scanner import main

if __name__ == "__main__":
    sys.exit(main())
