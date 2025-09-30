#!/usr/bin/env python3
"""
Interactive Database Manager for PinballUX
Easy-to-use interface for database operations
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from pinballux.src.core.config import Config
from pinballux.src.database.models import DatabaseManager
from pinballux.src.database.service import TableService
from pinballux.src.core.logger import setup_logging

def show_menu():
    """Display the main menu"""
    print("\n" + "=" * 50)
    print("       PinballUX Database Manager")
    print("=" * 50)
    print("1. Check for renamed/moved table files")
    print("2. Rescan all tables for updated metadata")
    print("3. Import new table files")
    print("4. Clean up missing table entries")
    print("5. Show database statistics")
    print("6. Validate all table files")
    print("0. Exit")
    print("=" * 50)

def show_statistics(table_service: TableService):
    """Show database statistics"""
    print("\nDatabase Statistics:")
    print("-" * 30)

    stats = table_service.get_table_statistics()
    print(f"Total tables: {stats['total_tables']}")
    print(f"Total plays: {stats['total_plays']}")
    print(f"Total play time: {stats['total_play_time_hours']:.1f} hours")
    print(f"Manufacturers: {stats['manufacturers_count']}")

    if stats['manufacturers']:
        print(f"Top manufacturers: {', '.join(stats['manufacturers'][:5])}")

def check_renamed_files(table_service: TableService, config: Config):
    """Check for renamed or moved files"""
    print("\nChecking for renamed/moved table files...")
    print("-" * 40)

    # First show what would happen
    validation = table_service.validate_table_files()

    print(f"Current status:")
    print(f"  Valid files: {len(validation['valid'])}")
    print(f"  Missing files: {len(validation['missing'])}")

    if validation['missing']:
        print(f"\nMissing files ({len(validation['missing'])}):")
        for missing in validation['missing'][:10]:  # Show first 10
            print(f"  {Path(missing).name}")
        if len(validation['missing']) > 10:
            print(f"  ... and {len(validation['missing']) - 10} more")

        response = input(f"\nAttempt to match missing files with renamed files? (y/n): ").lower()
        if response == 'y':
            result = table_service.update_database_for_renamed_files(config.vpx.table_directory)

            print(f"\nUpdate Results:")
            print(f"  Files matched: {result['matched']}")
            print(f"  Tables updated for renamed files: {len(result['renamed_tables'])}")
            print(f"  New files imported: {result['new_files']}")
            print(f"  Orphaned tables remaining: {result['orphaned'] - len(result['renamed_tables'])}")

            if result['renamed_tables']:
                print(f"\nSuccessfully matched renamed tables:")
                for renamed in result['renamed_tables']:
                    old_name = Path(renamed['old_path']).name
                    new_name = Path(renamed['new_path']).name
                    print(f"  {renamed['table_name']}: {old_name} -> {new_name}")
    else:
        print("All table files are accounted for!")

def rescan_tables(table_service: TableService):
    """Rescan all tables"""
    print("\nRescanning all tables for updated metadata...")
    print("-" * 45)

    response = input("This will update metadata for all tables. Continue? (y/n): ").lower()
    if response == 'y':
        result = table_service.rescan_all_tables()

        print(f"\nRescan Results:")
        print(f"  Total tables: {result['total']}")
        print(f"  Updated: {result['updated']}")
        print(f"  Missing files: {result['missing']}")
        print(f"  Errors: {result['errors']}")

def import_new_tables(table_service: TableService, config: Config):
    """Import new table files"""
    print("\nImporting new table files...")
    print("-" * 30)

    tables_dir = config.vpx.table_directory
    print(f"Scanning directory: {tables_dir}")

    result = table_service.scan_and_import_tables(tables_dir)

    print(f"\nImport Results:")
    print(f"  Files scanned: {result['scanned']}")
    print(f"  New tables: {result['new']}")
    print(f"  Updated tables: {result['updated']}")
    print(f"  Errors: {result['errors']}")

def cleanup_missing(table_service: TableService):
    """Clean up missing table entries"""
    print("\nCleaning up missing table entries...")
    print("-" * 35)

    validation = table_service.validate_table_files()

    if not validation['missing']:
        print("No missing table files found!")
        return

    print(f"Found {len(validation['missing'])} missing table files.")
    print("Options:")
    print("1. Disable missing tables (recommended)")
    print("2. Permanently remove missing tables")
    print("3. Cancel")

    choice = input("Choose option (1-3): ").strip()

    if choice == '1':
        result = table_service.remove_missing_tables(mark_disabled=True)
        print(f"\nDisabled {result['disabled']} tables with missing files")
    elif choice == '2':
        confirm = input("Are you sure you want to permanently remove these tables? (yes/no): ").lower()
        if confirm == 'yes':
            result = table_service.remove_missing_tables(mark_disabled=False)
            print(f"\nRemoved {result['removed']} tables with missing files")
        else:
            print("Operation cancelled")
    else:
        print("Operation cancelled")

def validate_files(table_service: TableService):
    """Validate all table files"""
    print("\nValidating all table files...")
    print("-" * 30)

    validation = table_service.validate_table_files()

    print(f"Validation Results:")
    print(f"  Valid files: {len(validation['valid'])}")
    print(f"  Missing files: {len(validation['missing'])}")
    print(f"  Inaccessible files: {len(validation['inaccessible'])}")

    if validation['missing']:
        print(f"\nMissing files:")
        for missing in validation['missing']:
            print(f"  {missing}")

    if validation['inaccessible']:
        print(f"\nInaccessible files:")
        for inaccessible in validation['inaccessible']:
            print(f"  {inaccessible}")

def main():
    """Main function"""
    print("Initializing PinballUX Database Manager...")

    # Set up logging
    setup_logging("INFO")

    # Load configuration
    try:
        config = Config()
        print(f"Tables directory: {config.vpx.table_directory}")
        print(f"Media directory: {config.vpx.media_directory}")
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1

    # Initialize services
    try:
        database_manager = DatabaseManager()
        database_manager.initialize()
        table_service = TableService(database_manager)
    except Exception as e:
        print(f"Error initializing database: {e}")
        return 1

    # Main loop
    while True:
        show_menu()

        try:
            choice = input("Select option (0-6): ").strip()

            if choice == '0':
                print("Goodbye!")
                break
            elif choice == '1':
                check_renamed_files(table_service, config)
            elif choice == '2':
                rescan_tables(table_service)
            elif choice == '3':
                import_new_tables(table_service, config)
            elif choice == '4':
                cleanup_missing(table_service)
            elif choice == '5':
                show_statistics(table_service)
            elif choice == '6':
                validate_files(table_service)
            else:
                print("Invalid option. Please try again.")

            if choice != '0':
                input("\nPress Enter to continue...")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            input("Press Enter to continue...")

    return 0

if __name__ == "__main__":
    sys.exit(main())