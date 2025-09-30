#!/usr/bin/env python3
"""
Database update utility for PinballUX
Handles renamed table files and database synchronization
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pinballux.src.core.config import Config
from pinballux.src.database.models import DatabaseManager
from pinballux.src.database.service import TableService
from pinballux.src.core.logger import setup_logging

def update_database_for_renamed_files(config: Config, dry_run: bool = False):
    """Update database to handle renamed table files"""

    print("PinballUX Database Update Utility")
    print("=" * 50)

    # Initialize services
    database_manager = DatabaseManager()
    database_manager.initialize()
    table_service = TableService(database_manager)

    tables_dir = config.vpx.table_directory

    if not os.path.exists(tables_dir):
        print(f"Error: Tables directory not found: {tables_dir}")
        return

    print(f"Scanning tables directory: {tables_dir}")
    print(f"Dry run mode: {'ON' if dry_run else 'OFF'}")
    print()

    if not dry_run:
        # Perform actual update
        result = table_service.update_database_for_renamed_files(tables_dir)

        print("Database Update Results:")
        print(f"  Files matched: {result['matched']}")
        print(f"  Orphaned tables: {result['orphaned']}")
        print(f"  New files found: {result['new_files']}")
        print(f"  Errors: {result['errors']}")

        if result['renamed_tables']:
            print(f"\nRenamed tables matched ({len(result['renamed_tables'])}):")
            for renamed in result['renamed_tables']:
                old_name = Path(renamed['old_path']).name
                new_name = Path(renamed['new_path']).name
                print(f"  {renamed['table_name']}: {old_name} -> {new_name}")

        if result['orphaned'] > len(result['renamed_tables']):
            unmatched = result['orphaned'] - len(result['renamed_tables'])
            print(f"\nWarning: {unmatched} orphaned tables could not be matched automatically")
            print("Consider running with --cleanup to remove missing tables")

    else:
        # Dry run - validate files only
        validation_result = table_service.validate_table_files()

        print("Validation Results (Dry Run):")
        print(f"  Valid files: {len(validation_result['valid'])}")
        print(f"  Missing files: {len(validation_result['missing'])}")
        print(f"  Inaccessible files: {len(validation_result['inaccessible'])}")

        if validation_result['missing']:
            print(f"\nMissing table files ({len(validation_result['missing'])}):")
            for missing_file in validation_result['missing']:
                print(f"  {missing_file}")

        if validation_result['inaccessible']:
            print(f"\nInaccessible table files ({len(validation_result['inaccessible'])}):")
            for inaccessible_file in validation_result['inaccessible']:
                print(f"  {inaccessible_file}")

def rescan_all_tables(config: Config):
    """Rescan all tables and update metadata"""

    print("Rescanning All Tables")
    print("=" * 30)

    # Initialize services
    database_manager = DatabaseManager()
    database_manager.initialize()
    table_service = TableService(database_manager)

    result = table_service.rescan_all_tables()

    print("Rescan Results:")
    print(f"  Total tables: {result['total']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Missing files: {result['missing']}")
    print(f"  Errors: {result['errors']}")

def cleanup_missing_tables(config: Config, remove_permanently: bool = False):
    """Clean up tables whose files no longer exist"""

    action = "remove" if remove_permanently else "disable"
    print(f"Cleaning Up Missing Tables ({action})")
    print("=" * 40)

    # Initialize services
    database_manager = DatabaseManager()
    database_manager.initialize()
    table_service = TableService(database_manager)

    result = table_service.remove_missing_tables(mark_disabled=not remove_permanently)

    print("Cleanup Results:")
    print(f"  Tables checked: {result['checked']}")
    print(f"  Missing files found: {result['missing']}")

    if remove_permanently:
        print(f"  Tables removed: {result['removed']}")
    else:
        print(f"  Tables disabled: {result['disabled']}")

def import_new_tables(config: Config):
    """Import new table files"""

    print("Importing New Tables")
    print("=" * 25)

    # Initialize services
    database_manager = DatabaseManager()
    database_manager.initialize()
    table_service = TableService(database_manager)

    tables_dir = config.vpx.table_directory

    if not os.path.exists(tables_dir):
        print(f"Error: Tables directory not found: {tables_dir}")
        return

    result = table_service.scan_and_import_tables(tables_dir)

    print("Import Results:")
    print(f"  Files scanned: {result['scanned']}")
    print(f"  New tables: {result['new']}")
    print(f"  Updated tables: {result['updated']}")
    print(f"  Errors: {result['errors']}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="PinballUX Database Update Utility")
    parser.add_argument('action', choices=['update', 'rescan', 'cleanup', 'import'],
                       help='Action to perform')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying database (update only)')
    parser.add_argument('--remove', action='store_true',
                       help='Permanently remove missing tables instead of disabling (cleanup only)')
    parser.add_argument('--config', type=str, help='Path to config file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    # Set up logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    # Load configuration
    try:
        config = Config(args.config)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1

    try:
        if args.action == 'update':
            update_database_for_renamed_files(config, dry_run=args.dry_run)
        elif args.action == 'rescan':
            rescan_all_tables(config)
        elif args.action == 'cleanup':
            cleanup_missing_tables(config, remove_permanently=args.remove)
        elif args.action == 'import':
            import_new_tables(config)

        print(f"\n{args.action.title()} operation completed successfully!")
        return 0

    except Exception as e:
        print(f"Error during {args.action} operation: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())