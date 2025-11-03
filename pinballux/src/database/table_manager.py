#!/usr/bin/env python3
"""
Table Manager - Automated table and media scanner for PinballUX

This standalone utility scans for VPX table files and associated media,
updates the database automatically, and reports what it finds.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure we can import from the src directory
import os
# Detect if we're in development (pinballux/src/...) or installed (/opt/pinballux/src/...)
file_path = Path(__file__).resolve()
if 'pinballux/src' in str(file_path):
    # Development: /home/keith/PinballUX/pinballux/src/database/table_manager.py
    script_dir = Path(__file__).parents[3]  # Go up to /home/keith/PinballUX/
else:
    # Installed: /opt/pinballux/src/database/table_manager.py
    script_dir = Path(__file__).parents[2]  # Go up to /opt/pinballux/
sys.path.insert(0, str(script_dir))
os.chdir(script_dir)

# Handle both development and installed import paths
try:
    from pinballux.src.core.config import Config
    from pinballux.src.core.logger import get_logger
    from pinballux.src.database.models import DatabaseManager
    from pinballux.src.database.service import TableService
    from pinballux.src.media.manager import MediaManager
except ModuleNotFoundError:
    from src.core.config import Config
    from src.core.logger import get_logger
    from src.database.models import DatabaseManager
    from src.database.service import TableService
    from src.media.manager import MediaManager


logger = get_logger(__name__)


class TableManager:
    """Automated table and media management"""

    def __init__(self):
        """Initialize the table manager"""
        print("=" * 80)
        print("PinballUX Table Manager")
        print("=" * 80)
        print()

        # Load configuration
        print("Loading configuration...")
        self.config = Config()

        # Initialize database
        print("Initializing database...")
        self.db_manager = DatabaseManager()
        self.db_manager.initialize()

        # Initialize media manager
        print("Initializing media manager...")
        self.media_manager = MediaManager(self.config)

        # Initialize table service
        self.table_service = TableService(self.db_manager, self.media_manager)

        print("✓ Initialization complete")
        print()

    def scan_and_report(self) -> Dict:
        """Scan for tables and media, update database, and report results"""

        results = {
            'tables': {},
            'media': {},
            'validation': {},
            'cleanup': {},
            'summary': {}
        }

        # 1. Clean up tables outside the current table directory
        print("Checking for tables outside current table directory...")
        outside_cleanup = self.table_service.remove_tables_outside_directory(
            self.config.vpx.table_directory,
            mark_disabled=False
        )

        if outside_cleanup['outside'] > 0:
            print(f"Found {outside_cleanup['outside']} tables outside current directory")
            print(f"✓ Removed {outside_cleanup['removed']} tables from database")
        else:
            print("✓ All tables are in current directory")
        print()

        # 2. Clean up missing/deleted tables
        print("Checking for deleted table files...")
        validation = self.table_service.validate_table_files()

        if validation['missing']:
            print(f"Found {len(validation['missing'])} deleted table files")
            print("Removing from database...")
            results['cleanup'] = self.table_service.remove_missing_tables(mark_disabled=False)
            print(f"✓ Removed {results['cleanup']['removed']} tables")
        else:
            print("✓ No deleted tables found")
            results['cleanup'] = {'checked': 0, 'missing': 0, 'removed': 0}
        print()

        # 2. Scan for table files (new and existing)
        print("Scanning for VPX table files...")
        print(f"Directory: {self.config.vpx.table_directory}")
        print()

        table_dir = Path(self.config.vpx.table_directory)
        if not table_dir.exists():
            print(f"✗ Table directory not found: {table_dir}")
            return results

        # Import/update tables
        results['tables'] = self.table_service.scan_and_import_tables(
            str(table_dir),
            recursive=True
        )

        # 3. Clear media paths outside the current media directory
        print("Checking for media files outside current media directory...")
        media_cleanup = self.table_service.clear_media_outside_directory(
            self.config.vpx.media_directory
        )

        if media_cleanup['cleared'] > 0:
            print(f"Found {media_cleanup['cleared']} tables with media outside current directory")
            print(f"✓ Cleared media paths (will be re-scanned)")
        else:
            print("✓ All media paths are in current directory")
        print()

        # 4. Scan for media files
        print("Scanning for media files...")
        print(f"Directory: {self.config.vpx.media_directory}")
        print()

        media_dir = Path(self.config.vpx.media_directory)
        if media_dir.exists():
            results['media'] = self.table_service.rescan_all_media()
        else:
            print(f"✗ Media directory not found: {media_dir}")
            results['media'] = {'total': 0, 'updated': 0, 'errors': 0}

        # 4. Final validation
        print("\nValidating table files...")
        results['validation'] = self.table_service.validate_table_files()

        # 5. Get all tables for summary
        all_tables = self.table_service.get_all_tables(enabled_only=False)
        results['summary']['total_tables'] = len(all_tables)

        # Get statistics
        stats = self.table_service.get_table_statistics()
        results['summary']['statistics'] = stats

        return results

    def print_report(self, results: Dict):
        """Print formatted report of scan results"""

        print()
        print("=" * 80)
        print("SCAN RESULTS")
        print("=" * 80)
        print()

        # Cleanup results
        if results.get('cleanup') and results['cleanup'].get('removed', 0) > 0:
            c = results['cleanup']
            print("🗑️  CLEANUP:")
            print(f"   Removed:  {c.get('removed', 0)} deleted tables from database")
            print()

        # Table scan results
        if results.get('tables'):
            t = results['tables']
            print("📀 TABLE FILES:")
            print(f"   Scanned:  {t.get('scanned', 0)} files")
            print(f"   New:      {t.get('new', 0)} tables added")
            print(f"   Updated:  {t.get('updated', 0)} tables updated")
            if t.get('errors', 0) > 0:
                print(f"   Errors:   {t.get('errors', 0)} ⚠️")
            print()

        # Media scan results
        if results.get('media'):
            m = results['media']
            print("🎬 MEDIA FILES:")
            print(f"   Tables:   {m.get('total', 0)} tables processed")
            print(f"   Updated:  {m.get('updated', 0)} tables with media found")
            print(f"   Missing:  {m.get('no_changes', 0)} tables with no media changes")
            if m.get('errors', 0) > 0:
                print(f"   Errors:   {m.get('errors', 0)} ⚠️")
            print()

        # Validation results
        if results.get('validation'):
            v = results['validation']
            total = len(v.get('valid', [])) + len(v.get('missing', [])) + len(v.get('inaccessible', []))
            print("✓ VALIDATION:")
            print(f"   Valid:    {len(v.get('valid', []))} / {total} files")

            if v.get('missing'):
                print(f"   Missing:  {len(v['missing'])} files ⚠️")
                for path in v['missing'][:5]:  # Show first 5
                    print(f"      - {Path(path).name}")
                if len(v['missing']) > 5:
                    print(f"      ... and {len(v['missing']) - 5} more")

            if v.get('inaccessible'):
                print(f"   Bad:      {len(v['inaccessible'])} files ⚠️")
            print()

        # Summary statistics
        if results.get('summary', {}).get('statistics'):
            stats = results['summary']['statistics']
            print("📊 DATABASE STATISTICS:")
            print(f"   Total Tables:    {stats.get('total_tables', 0)}")
            print(f"   Manufacturers:   {stats.get('manufacturers_count', 0)}")
            print(f"   Total Plays:     {stats.get('total_plays', 0)}")
            print(f"   Play Time:       {stats.get('total_play_time_hours', 0):.1f} hours")
            print()

        # Get detailed table info
        all_tables = self.table_service.get_all_tables(enabled_only=True)

        if all_tables:
            print("📋 TABLES IN DATABASE:")

            # Group by manufacturer
            by_manufacturer: Dict[str, List] = {}
            for table in all_tables:
                mfr = table.manufacturer or "Unknown"
                if mfr not in by_manufacturer:
                    by_manufacturer[mfr] = []
                by_manufacturer[mfr].append(table)

            # Print by manufacturer
            for mfr in sorted(by_manufacturer.keys()):
                tables = by_manufacturer[mfr]
                print(f"\n   {mfr} ({len(tables)} tables):")
                for table in sorted(tables, key=lambda t: t.name):
                    # Check media availability
                    media_icons = []
                    if table.table_video:
                        media_icons.append("🎬")
                    if table.backglass_video or table.backglass_image:
                        media_icons.append("🖼️")
                    if table.table_audio:
                        media_icons.append("🔊")

                    media_str = "".join(media_icons) if media_icons else "   "
                    year_str = f" ({table.year})" if table.year else ""

                    print(f"      {media_str}  {table.name}{year_str}")
            print()

        print("=" * 80)
        print("✓ Scan complete!")
        print("=" * 80)

    def run(self):
        """Run the table manager"""
        try:
            # Perform scan
            results = self.scan_and_report()

            # Print report
            self.print_report(results)

            return 0

        except KeyboardInterrupt:
            print("\n\n✗ Interrupted by user")
            return 1
        except Exception as e:
            print(f"\n\n✗ Error: {e}")
            logger.exception("Error running table manager")
            return 1


def main():
    """Main entry point"""
    manager = TableManager()
    return manager.run()


if __name__ == "__main__":
    sys.exit(main())
