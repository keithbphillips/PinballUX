#!/usr/bin/env python3
"""
Script to organize backglass files from tables directory into proper media structure
"""

import sys
import os
import shutil
from pathlib import Path

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pinballux.src.core.logger import setup_logging

def organize_backglass_files():
    """Organize backglass files into proper media structure"""

    setup_logging("INFO")

    # Source and destination directories
    tables_dir = Path.cwd() / "tables"
    media_dir = Path.cwd() / "Media" / "Visual Pinball"
    backglass_dir = media_dir / "Backglass Images"

    # Create backglass directory if it doesn't exist
    backglass_dir.mkdir(parents=True, exist_ok=True)

    print(f"Organizing backglass files...")
    print(f"Source directory: {tables_dir}")
    print(f"Destination directory: {backglass_dir}")
    print("=" * 60)

    # Find all .directb2s files in tables directory
    backglass_files = list(tables_dir.glob("*.directb2s")) + list(tables_dir.glob("*.directB2S"))

    if not backglass_files:
        print("No backglass files found in tables directory")
        return

    print(f"Found {len(backglass_files)} backglass files:")

    copied_count = 0
    skipped_count = 0

    for backglass_file in backglass_files:
        print(f"\nProcessing: {backglass_file.name}")

        # Skip zone identifier files
        if ":Zone.Identifier" in backglass_file.name:
            print("  Skipped: Zone identifier file")
            skipped_count += 1
            continue

        # Extract table name from filename (remove .directb2s extension)
        table_name = backglass_file.stem

        # Create destination filename (convert to .png for consistency)
        # But keep original extension for backglass files
        dest_filename = backglass_file.name
        dest_path = backglass_dir / dest_filename

        try:
            if dest_path.exists():
                print(f"  Skipped: File already exists in media directory")
                skipped_count += 1
                continue

            # Copy the file
            shutil.copy2(backglass_file, dest_path)
            print(f"  Copied to: {dest_path}")
            copied_count += 1

        except Exception as e:
            print(f"  Error copying file: {e}")

    print("\n" + "=" * 60)
    print(f"Organization complete!")
    print(f"Files copied: {copied_count}")
    print(f"Files skipped: {skipped_count}")

    # Also check if we should create image versions of the backglass files
    if copied_count > 0:
        print(f"\nNote: Backglass files have been copied to the media directory.")
        print(f"The media system will automatically detect them for table backglass display.")
        print(f"Location: {backglass_dir}")


def show_media_structure():
    """Show the current media directory structure"""
    media_dir = Path.cwd() / "Media" / "Visual Pinball"

    print(f"\nCurrent media directory structure:")
    print(f"Root: {media_dir}")

    if not media_dir.exists():
        print("Media directory does not exist")
        return

    for category_dir in media_dir.iterdir():
        if category_dir.is_dir():
            file_count = len(list(category_dir.glob("*")))
            print(f"  {category_dir.name}: {file_count} files")


if __name__ == "__main__":
    organize_backglass_files()
    show_media_structure()