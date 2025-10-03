#!/usr/bin/env python3
"""
PinballUX - Media Pack Importer
Imports media files from Visual Pinball media pack ZIP files
"""

import sys
import os
from pathlib import Path
import zipfile
import shutil
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pinballux.src.core.config import Config
from pinballux.src.database.models import DatabaseManager
from pinballux.src.database.service import TableService


def similarity_ratio(str1: str, str2: str) -> float:
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def find_visual_pinball_dir(zip_ref: zipfile.ZipFile) -> Optional[str]:
    """Find the Visual Pinball directory in the zip file"""
    for name in zip_ref.namelist():
        if 'visual pinball' in name.lower() and name.endswith('/'):
            return name
    return None


def find_media_subdirs(zip_ref: zipfile.ZipFile, vp_dir: str) -> Dict[str, str]:
    """Find media subdirectories within Visual Pinball directory"""
    subdirs = {
        'backglass': None,
        'table': None,
        'wheel': None
    }

    # Common directory name variations
    patterns = {
        'backglass': ['backglass', 'back glass', 'bg'],
        'table': ['table', 'playfield', 'pf'],
        'wheel': ['wheel', 'logo']
    }

    for name in zip_ref.namelist():
        if not name.startswith(vp_dir) or not name.endswith('/'):
            continue

        dir_name = name[len(vp_dir):].strip('/').lower()

        # Check if directory name contains any pattern
        for media_type, pattern_list in patterns.items():
            if subdirs[media_type] is None:  # Only set if not already found
                for pattern in pattern_list:
                    if pattern in dir_name and 'image' in dir_name:
                        subdirs[media_type] = name
                        break

    return subdirs


def extract_media_files(zip_ref: zipfile.ZipFile, media_dir: str) -> List[Tuple[str, str]]:
    """Extract media files from a directory in the zip"""
    if not media_dir:
        return []

    files = []
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}

    for name in zip_ref.namelist():
        if name.startswith(media_dir) and not name.endswith('/'):
            ext = Path(name).suffix.lower()
            if ext in image_extensions:
                filename = Path(name).name
                files.append((name, filename))

    return files


def match_file_to_tables(filename: str, tables: List) -> List[Tuple[any, float]]:
    """Match a filename to tables in the database, return list of (table, score) sorted by score"""
    # Remove extension and clean filename
    clean_filename = Path(filename).stem

    matches = []
    for table in tables:
        # Try matching against table name
        score = similarity_ratio(clean_filename, table.name)

        # Also try with manufacturer and year
        if table.manufacturer and table.year:
            full_name = f"{table.name} ({table.manufacturer} {table.year})"
            score2 = similarity_ratio(clean_filename, full_name)
            score = max(score, score2)

        if score > 0.5:  # Only consider matches above 50%
            matches.append((table, score))

    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


class MediaPackImporter:
    """Import media packs from ZIP files"""

    def __init__(self):
        print("=" * 80)
        print("PinballUX Media Pack Importer")
        print("=" * 80)
        print()

        # Load configuration
        print("Loading configuration...")
        self.config = Config()

        # Initialize database
        print("Initializing database...")
        self.db_manager = DatabaseManager()
        self.db_manager.initialize()
        self.table_service = TableService(self.db_manager)

        # Get all tables
        self.tables = self.table_service.get_all_tables(enabled_only=True)
        print(f"✓ Found {len(self.tables)} tables in database")
        print()

        # Media pack directory
        self.pack_dir = Path(self.config.vpx.media_directory) / "packs"
        self.pack_dir.mkdir(parents=True, exist_ok=True)

        # Destination directories
        self.dest_dirs = {
            'backglass': Path(self.config.vpx.media_directory) / "images" / "backglass",
            'table': Path(self.config.vpx.media_directory) / "images" / "table",
            'wheel': Path(self.config.vpx.media_directory) / "images" / "wheel"
        }

        # Ensure destination directories exist
        for dest_dir in self.dest_dirs.values():
            dest_dir.mkdir(parents=True, exist_ok=True)

    def find_packs(self) -> List[Path]:
        """Find all ZIP files in the packs directory"""
        return list(self.pack_dir.glob("*.zip"))

    def process_pack(self, pack_path: Path):
        """Process a single media pack ZIP file"""
        print(f"\nProcessing: {pack_path.name}")
        print("-" * 80)

        try:
            with zipfile.ZipFile(pack_path, 'r') as zip_ref:
                # Find Visual Pinball directory
                vp_dir = find_visual_pinball_dir(zip_ref)
                if not vp_dir:
                    print("✗ Could not find 'Visual Pinball' directory in ZIP file")
                    return

                print(f"✓ Found Visual Pinball directory: {vp_dir}")

                # Find media subdirectories
                media_dirs = find_media_subdirs(zip_ref, vp_dir)

                found_types = [k for k, v in media_dirs.items() if v]
                if not found_types:
                    print("✗ Could not find any media subdirectories (Backglass Images, Table Images, Wheel Images)")
                    return

                print(f"✓ Found media types: {', '.join(found_types)}")
                print()

                # Process each media type
                stats = {
                    'total': 0,
                    'matched': 0,
                    'imported': 0,
                    'skipped': 0
                }

                for media_type, media_dir in media_dirs.items():
                    if not media_dir:
                        continue

                    print(f"\n{media_type.upper()} IMAGES:")
                    print("-" * 40)

                    files = extract_media_files(zip_ref, media_dir)
                    if not files:
                        print(f"  No files found")
                        continue

                    print(f"  Found {len(files)} files")
                    stats['total'] += len(files)

                    for zip_path, filename in files:
                        # Try to match to a table
                        matches = match_file_to_tables(filename, self.tables)

                        if not matches:
                            print(f"\n  ✗ {filename}")
                            print(f"    No matching table found (skipping)")
                            stats['skipped'] += 1
                            continue

                        # Show best match
                        best_table, best_score = matches[0]
                        print(f"\n  📄 {filename}")
                        print(f"    Best match: {best_table.display_name} ({best_score*100:.0f}% confidence)")

                        # Ask for confirmation
                        response = input(f"    Import as {best_table.name}? [Y/n/s(kip all)]: ").strip().lower()

                        if response == 's':
                            print("    Skipping remaining files in this category...")
                            stats['skipped'] += len(files) - files.index((zip_path, filename))
                            break
                        elif response == 'n':
                            print("    Skipped")
                            stats['skipped'] += 1
                            continue

                        # Import the file
                        try:
                            # Extract to temporary location
                            temp_path = Path("/tmp") / filename
                            with zip_ref.open(zip_path) as source, open(temp_path, 'wb') as dest:
                                dest.write(source.read())

                            # Determine destination filename (use table name + extension)
                            ext = Path(filename).suffix
                            dest_filename = f"{best_table.name}{ext}"
                            dest_path = self.dest_dirs[media_type] / dest_filename

                            # Copy to destination
                            shutil.copy2(temp_path, dest_path)
                            temp_path.unlink()

                            print(f"    ✓ Imported as: {dest_filename}")
                            stats['matched'] += 1
                            stats['imported'] += 1

                        except Exception as e:
                            print(f"    ✗ Error importing: {e}")
                            stats['skipped'] += 1

                # Print summary
                print("\n" + "=" * 80)
                print("IMPORT SUMMARY")
                print("=" * 80)
                print(f"Total files:     {stats['total']}")
                print(f"Matched:         {stats['matched']}")
                print(f"Imported:        {stats['imported']}")
                print(f"Skipped:         {stats['skipped']}")
                print()

        except zipfile.BadZipFile:
            print(f"✗ Error: Not a valid ZIP file")
        except Exception as e:
            print(f"✗ Error processing pack: {e}")

    def run(self):
        """Run the media pack importer"""
        try:
            # Find packs
            packs = self.find_packs()

            if not packs:
                print(f"No media packs found in: {self.pack_dir}")
                print(f"\nPlace your Visual Pinball media pack ZIP files in this directory,")
                print(f"then run this script again.")
                return 0

            print(f"Found {len(packs)} media pack(s) in: {self.pack_dir}")
            print()

            # Process each pack
            for pack_path in packs:
                self.process_pack(pack_path)

            print("\n✓ Media pack import complete!")
            print("\nRun 'python scan_tables.py' to update the table database with new media files.")

            return 0

        except KeyboardInterrupt:
            print("\n\n✗ Interrupted by user")
            return 1
        except Exception as e:
            print(f"\n\n✗ Error: {e}")
            return 1


def main():
    """Main entry point"""
    importer = MediaPackImporter()
    return importer.run()


if __name__ == "__main__":
    sys.exit(main())
