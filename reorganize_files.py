#!/usr/bin/env python3
"""
Script to reorganize tables and media files to proper PinballUX structure
"""

import sys
import os
import shutil
from pathlib import Path

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pinballux.src.core.logger import setup_logging

def reorganize_files():
    """Reorganize files to proper PinballUX directory structure"""

    setup_logging("INFO")

    print("Reorganizing PinballUX Files...")
    print("=" * 60)

    # Define source and destination paths
    current_tables_dir = Path.cwd() / "tables"
    current_media_dir = Path.cwd() / "Media"

    pinballux_tables_dir = Path.cwd() / "pinballux" / "data" / "tables"
    pinballux_media_dir = Path.cwd() / "pinballux" / "data" / "media"

    # Move tables
    if current_tables_dir.exists():
        print(f"\n1. Moving tables from {current_tables_dir} to {pinballux_tables_dir}")

        # Count VPX and directb2s files
        vpx_files = list(current_tables_dir.glob("*.vpx"))
        directb2s_files = list(current_tables_dir.glob("*.directb2s")) + list(current_tables_dir.glob("*.directB2S"))

        print(f"   Found {len(vpx_files)} VPX files")
        print(f"   Found {len(directb2s_files)} DirectB2S files")

        # Move VPX files
        moved_vpx = 0
        for vpx_file in vpx_files:
            if ":Zone.Identifier" not in vpx_file.name:
                dest_file = pinballux_tables_dir / vpx_file.name
                try:
                    shutil.move(str(vpx_file), str(dest_file))
                    moved_vpx += 1
                    print(f"   Moved: {vpx_file.name}")
                except Exception as e:
                    print(f"   Error moving {vpx_file.name}: {e}")

        print(f"   Successfully moved {moved_vpx} VPX files")

        # Move DirectB2S files to media backglass directory
        media_backglass_dir = pinballux_media_dir / "images" / "backglass"
        media_backglass_dir.mkdir(parents=True, exist_ok=True)

        moved_directb2s = 0
        for directb2s_file in directb2s_files:
            if ":Zone.Identifier" not in directb2s_file.name:
                dest_file = media_backglass_dir / directb2s_file.name
                try:
                    shutil.move(str(directb2s_file), str(dest_file))
                    moved_directb2s += 1
                    print(f"   Moved to backglass: {directb2s_file.name}")
                except Exception as e:
                    print(f"   Error moving {directb2s_file.name}: {e}")

        print(f"   Successfully moved {moved_directb2s} DirectB2S files to backglass directory")
    else:
        print(f"\n1. Tables directory {current_tables_dir} not found - skipping")

    # Move media files
    if current_media_dir.exists():
        print(f"\n2. Moving media from {current_media_dir} to {pinballux_media_dir}")

        # Create new media structure that matches PinballX
        media_structure = {
            "Visual Pinball/Table Images": "images/table",
            "Visual Pinball/Table Videos": "videos/table",
            "Visual Pinball/Backglass Images": "images/backglass",
            "Visual Pinball/Backglass Videos": "videos/backglass",
            "Visual Pinball/DMD Images": "images/dmd",
            "Visual Pinball/DMD Videos": "videos/dmd",
            "Visual Pinball/Topper Images": "images/topper",
            "Visual Pinball/Topper Videos": "videos/topper",
            "Visual Pinball/Wheel Images": "images/wheel",
            "Visual Pinball/Table Audio": "audio/table",
            "Visual Pinball/Launch Audio": "audio/launch",
            "Visual Pinball/Real DMD Color Videos": "videos/real_dmd_color",
            "Visual Pinball/Real DMD Videos": "videos/real_dmd",
            "Visual Pinball/Real DMD Images": "images/real_dmd",
            "Visual Pinball/FullDMD Videos": "videos/fulldmd",
            "Visual Pinball/Default Images": "images/default",
            "Visual Pinball/Default Videos": "videos/default"
        }

        total_moved = 0
        for source_path, dest_path in media_structure.items():
            source_full = current_media_dir / source_path
            dest_full = pinballux_media_dir / dest_path

            if source_full.exists():
                # Create destination directory
                dest_full.mkdir(parents=True, exist_ok=True)

                # Move files
                files = [f for f in source_full.iterdir() if f.is_file()]
                moved_count = 0

                for file in files:
                    dest_file = dest_full / file.name
                    try:
                        shutil.move(str(file), str(dest_file))
                        moved_count += 1
                        total_moved += 1
                    except Exception as e:
                        print(f"   Error moving {file.name}: {e}")

                if moved_count > 0:
                    print(f"   {source_path}: moved {moved_count} files")

        print(f"   Total media files moved: {total_moved}")

        # Remove empty directories
        try:
            if current_media_dir.exists():
                # Remove empty subdirectories first
                for item in current_media_dir.rglob('*'):
                    if item.is_dir() and not any(item.iterdir()):
                        item.rmdir()

                # Remove main directory if empty
                if not any(current_media_dir.iterdir()):
                    current_media_dir.rmdir()
                    print(f"   Removed empty media directory: {current_media_dir}")
        except Exception as e:
            print(f"   Note: Could not remove empty directories: {e}")
    else:
        print(f"\n2. Media directory {current_media_dir} not found - skipping")

    # Update the configuration and code to point to new locations
    print(f"\n3. Updating configuration...")

    # Update default config to point to new directories
    config_file = Path.cwd() / "pinballux" / "src" / "core" / "config.py"
    if config_file.exists():
        print(f"   Note: You may want to update the default paths in {config_file}")
        print(f"   New tables directory: {pinballux_tables_dir}")
        print(f"   New media directory: {pinballux_media_dir}")

    print(f"\n4. Summary:")
    print(f"   Tables are now in: {pinballux_tables_dir}")
    print(f"   Media is now in: {pinballux_media_dir}")
    print(f"   The application will need to be updated to use these new paths")

    # Create a quick verification
    print(f"\n5. Verification:")
    if pinballux_tables_dir.exists():
        vpx_count = len(list(pinballux_tables_dir.glob("*.vpx")))
        print(f"   VPX files in new location: {vpx_count}")

    if pinballux_media_dir.exists():
        media_count = sum(1 for f in pinballux_media_dir.rglob("*") if f.is_file())
        print(f"   Media files in new location: {media_count}")

    print(f"\nReorganization complete!")
    print(f"You can now delete the original 'tables' directory if it's empty.")


if __name__ == "__main__":
    reorganize_files()