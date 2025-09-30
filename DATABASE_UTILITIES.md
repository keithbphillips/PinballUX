# PinballUX Database Utilities

This document describes how to use the database utilities for managing table files and database updates in PinballUX.

## Quick Start

The easiest way to manage your database is with the interactive Database Manager:

```bash
python database_manager.py
```

This provides a menu-driven interface for all database operations.

## Command Line Utilities

For scripting or advanced users, use the command-line utility:

```bash
python update_database.py [action] [options]
```

### Available Actions

#### 1. Import New Tables
Import all VPX files from the tables directory into the database:

```bash
python update_database.py import
```

This will:
- Scan the configured tables directory for .vpx files
- Parse metadata from each file
- Add new tables to the database
- Update existing tables if files have changed

#### 2. Update Database for Renamed Files
Handle renamed or moved table files:

```bash
# Preview changes without modifying database
python update_database.py update --dry-run

# Perform actual update
python update_database.py update
```

This will:
- Compare files in the tables directory with database entries
- Attempt to match orphaned database entries with renamed files using metadata
- Update file paths for successfully matched tables
- Import any completely new files

#### 3. Rescan All Tables
Update metadata for all existing tables:

```bash
python update_database.py rescan
```

This will:
- Re-examine all VPX files referenced in the database
- Update metadata if files have changed
- Report missing files

#### 4. Clean Up Missing Tables
Remove or disable tables whose files no longer exist:

```bash
# Disable missing tables (recommended)
python update_database.py cleanup

# Permanently remove missing tables (destructive!)
python update_database.py cleanup --remove
```

### Options

- `--dry-run`: Preview changes without modifying the database (update action only)
- `--remove`: Permanently remove instead of disabling (cleanup action only)
- `--config PATH`: Use a specific configuration file
- `--verbose`: Enable detailed logging

## Common Scenarios

### Scenario 1: After Moving Table Files
If you've moved your table files to a new directory:

1. Update your PinballUX configuration to point to the new directory
2. Run: `python update_database.py update`
3. Run: `python update_database.py cleanup` to clean up orphaned entries

### Scenario 2: After Renaming Table Files
If you've renamed some table files:

1. Run: `python update_database.py update --dry-run` to see what would happen
2. Run: `python update_database.py update` to update the database
3. Check the results - successfully matched files will be updated

### Scenario 3: Adding New Tables
If you've added new VPX files to your tables directory:

1. Run: `python update_database.py import`

### Scenario 4: After Table File Updates
If table authors have released updated versions of tables:

1. Replace the old .vpx files with new ones
2. Run: `python update_database.py rescan` to update metadata

## File Matching Algorithm

When detecting renamed files, the system uses a scoring algorithm based on:

- **Table name** (highest priority): Exact match (10 points), partial match (5-7 points)
- **Manufacturer**: Exact match (3 points)
- **Year**: Exact match (2 points)
- **Author**: Exact match (2 points)
- **ROM name**: Exact match (2 points)
- **File size**: Exact match (2 points), close match within 1MB (1 point)

A minimum score of 5 points is required for an automatic match.

## Database Location

The database is stored at: `~/.config/pinballux/pinballux.db`

## Backup Recommendation

Before performing destructive operations (like `cleanup --remove`), consider backing up your database:

```bash
cp ~/.config/pinballux/pinballux.db ~/.config/pinballux/pinballux.db.backup
```

## Integration with PinballUX

These utilities are designed to work with the main PinballUX application. After updating the database, restart PinballUX to see the changes.

The application will automatically:
- Load tables from the updated database
- Display current table counts in the wheel interface
- Preserve user data like play counts and favorites (even for renamed files)

## Troubleshooting

### "Database not initialized" Error
If you see this error, the database needs to be created first:
```bash
python update_database.py import
```

### Tables Not Appearing in PinballUX
1. Check that your configuration points to the correct tables directory
2. Ensure tables are enabled: check with `python update_database.py update --dry-run`
3. Restart the PinballUX application

### Missing Table Files
Use the cleanup command to handle tables whose files no longer exist:
```bash
python update_database.py cleanup
```