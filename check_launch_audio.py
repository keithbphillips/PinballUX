#!/usr/bin/env python3
"""Check launch audio configuration for tables"""

import sys
from pathlib import Path

# Add the pinballux module to the path
sys.path.insert(0, str(Path(__file__).parent))

from pinballux.src.database.service import TableService, DatabaseManager
from pinballux.src.media.manager import MediaManager
from pinballux.src.core.config import Config

# Load config
config = Config()

# Initialize services
db_manager = DatabaseManager()
db_manager.initialize()  # Initialize the database
table_service = TableService(db_manager)
media_manager = MediaManager(config)

# Get all tables
tables = table_service.get_all_tables()

print(f"Found {len(tables)} tables in database\n")

# Check first 5 tables for launch audio
for i, table in enumerate(tables[:5], 1):
    print(f"{i}. {table.name}")
    print(f"   Manufacturer: {table.manufacturer}")
    print(f"   Year: {table.year}")
    print(f"   DB launch_audio: {table.launch_audio or '(not set)'}")

    # Find media files
    media_files = media_manager.find_table_media(table.name, table.manufacturer, table.year)
    print(f"   Media launch_audio: {media_files.get('launch_audio') or '(not found)'}")
    print()

# List available launch audio files
launch_audio_dir = Path(config.vpx.media_directory) / "audio" / "launch"
if launch_audio_dir.exists():
    print(f"\nAvailable launch audio files in {launch_audio_dir}:")
    for f in sorted(launch_audio_dir.glob("*.mp3")):
        print(f"  - {f.name}")
