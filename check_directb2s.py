#!/usr/bin/env python3
"""
Check if VPX tables have corresponding .directb2s backglass files
"""

import sys
from pathlib import Path


def check_directb2s(table_path):
    """Check if a table has a corresponding .directb2s file"""
    table_path = Path(table_path)

    if not table_path.exists():
        return False, "Table file not found"

    # Get the base name without extension
    base_name = table_path.stem

    # Check for .directb2s file in same directory (case-insensitive)
    # Try common variations: .directb2s, .directb2S, .DirectB2S
    possible_extensions = ['.directb2s', '.directb2S', '.DirectB2S', '.DIRECTB2S']

    for ext in possible_extensions:
        directb2s_path = table_path.parent / f"{base_name}{ext}"
        if directb2s_path.exists():
            return True, str(directb2s_path)

    return False, "No .directb2s file found"


def scan_directory(directory):
    """Scan a directory for VPX tables and check for .directb2s files"""
    directory = Path(directory)

    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return

    # Find all .vpx files
    vpx_files = list(directory.glob("*.vpx"))

    if not vpx_files:
        print(f"No .vpx files found in {directory}")
        return

    print(f"\nChecking {len(vpx_files)} tables in {directory}\n")
    print("=" * 80)

    has_b2s = []
    missing_b2s = []

    for vpx_file in sorted(vpx_files):
        has_file, info = check_directb2s(vpx_file)

        if has_file:
            has_b2s.append(vpx_file.name)
            print(f"✓ {vpx_file.name}")
        else:
            missing_b2s.append(vpx_file.name)
            print(f"✗ {vpx_file.name}")

    print("=" * 80)
    print(f"\nSummary:")
    print(f"  Tables with .directb2s: {len(has_b2s)}")
    print(f"  Tables missing .directb2s: {len(missing_b2s)}")
    print(f"  Coverage: {len(has_b2s)}/{len(vpx_files)} ({len(has_b2s)/len(vpx_files)*100:.1f}%)")

    if missing_b2s and len(missing_b2s) <= 10:
        print(f"\nMissing .directb2s files:")
        for table in missing_b2s:
            print(f"  - {table}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} <table.vpx>         - Check a specific table")
        print(f"  {sys.argv[0]} <directory>         - Check all tables in directory")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file():
        # Check single file
        has_file, info = check_directb2s(path)

        if has_file:
            print(f"✓ {path.name} has .directb2s file")
            print(f"  Location: {info}")
        else:
            print(f"✗ {path.name} does NOT have .directb2s file")

    elif path.is_dir():
        # Scan directory
        scan_directory(path)

    else:
        print(f"Error: Not a valid file or directory: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
