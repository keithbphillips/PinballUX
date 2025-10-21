#!/usr/bin/env python3
"""
configure_jukebox_launchers.py - Configure custom launchers for Jukebox tables

This script automatically configures the custom launcher field for all tables
that have a "launch_jukebox.sh" script in their directory.

Usage:
    python3 configure_jukebox_launchers.py
"""

import sys
from pathlib import Path

# Add pinballux package to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pinballux.src.database.models import DatabaseManager, Table


def configure_jukebox_tables():
    """Configure custom launchers for all Jukebox tables"""
    print("Configuring custom launchers for Jukebox tables...")
    print()

    db = DatabaseManager()
    db.initialize()

    with db.get_session() as session:
        # Find all tables with "Jukebox" in the name
        tables = session.query(Table).filter(
            Table.name.like("%Jukebox%")
        ).all()

        if not tables:
            print("No Jukebox tables found in database")
            print("Make sure you've scanned your tables first")
            return

        print(f"Found {len(tables)} Jukebox table(s):")
        for table in tables:
            print(f"  - {table.name}")
        print()

        updated = 0
        for table in tables:
            table_dir = Path(table.file_path).parent
            launcher_script = table_dir / "launch_jukebox.sh"

            print(f"Checking: {table.name}")
            print(f"  Table path: {table.file_path}")
            print(f"  Looking for: {launcher_script}")

            if launcher_script.exists():
                # Verify it's executable
                if not launcher_script.stat().st_mode & 0o111:
                    print(f"  ✗ Script exists but is NOT executable")
                    print(f"    Run: chmod +x {launcher_script}")
                    print()
                    continue

                # Set custom launcher
                table.custom_launcher = "launch_jukebox.sh"
                updated += 1
                print(f"  ✓ Configured custom launcher: launch_jukebox.sh")
            else:
                print(f"  ✗ Launcher script not found")
                print(f"    Create: {launcher_script}")

            print()

        if updated > 0:
            session.commit()
            print(f"Successfully configured {updated} table(s)")
            print()
            print("Tables will now use launch_jukebox.sh when launched from PinballUX")
        else:
            print("No tables were updated")
            print()
            print("Make sure:")
            print("  1. launch_jukebox.sh exists in each table's directory")
            print("  2. Scripts are executable (chmod +x launch_jukebox.sh)")


def list_all_tables():
    """List all tables in the database"""
    print("All tables in database:")
    print()

    db = DatabaseManager()
    db.initialize()

    with db.get_session() as session:
        tables = session.query(Table).order_by(Table.name).all()

        if not tables:
            print("No tables found in database")
            return

        for table in tables:
            launcher_status = "custom" if table.custom_launcher else "default"
            print(f"  [{launcher_status}] {table.name}")
            if table.custom_launcher:
                print(f"           Launcher: {table.custom_launcher}")

        print()
        print(f"Total: {len(tables)} table(s)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Configure custom launchers for Jukebox tables"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all tables and their launcher status"
    )

    args = parser.parse_args()

    if args.list:
        list_all_tables()
    else:
        configure_jukebox_tables()
