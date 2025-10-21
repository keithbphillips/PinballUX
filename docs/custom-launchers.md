# Custom Table Launchers

PinballUX supports custom launch scripts for tables that require special handling or alternative launchers instead of the standard VPinballX_GL executable.

## Overview

By default, PinballUX launches VPX tables using Visual Pinball Standalone (VPinballX_GL). However, some tables may need:
- Custom startup scripts
- Environment setup
- Alternative executables
- Special command-line arguments
- Wrapper scripts

## How It Works

1. **Custom Launcher Field**: Each table in the database has an optional `custom_launcher` field
2. **Relative Path**: The launcher path is relative to the table's directory
3. **Executable Script**: The script must be executable (`chmod +x`)
4. **Working Directory**: The script runs with the table directory as the working directory

## Setting Up a Custom Launcher

### Option 1: Direct Database Update

You can update the database directly using Python:

```python
from pinballux.src.database.models import DatabaseManager

# Initialize database
db = DatabaseManager()
db.initialize()

# Get table by name or path
with db.get_session() as session:
    from pinballux.src.database.models import Table

    # Find your table
    table = session.query(Table).filter(Table.name.like("%Jukebox%")).first()

    if table:
        # Set custom launcher (relative to table directory)
        table.custom_launcher = "launch_jukebox.sh"
        session.commit()
        print(f"Custom launcher set for: {table.name}")
```

### Option 2: Configuration File

You can also configure custom launchers in your PinballUX config file (`~/.config/pinballux/config.json`):

```json
{
  "custom_launchers": {
    "Jukebox_table_1.vpx": "launch_jukebox.sh",
    "Jukebox_table_2.vpx": "launch_jukebox.sh"
  }
}
```

### Option 3: Auto-Detection

PinballUX can auto-detect custom launchers by looking for specific script names in the table directory:
- `launch.sh`
- `start.sh`
- `run.sh`

## Example: Jukebox Tables

For your Jukebox tables, the setup would be:

```bash
# Table directory structure
/path/to/tables/Jukebox_Table_1/
├── Jukebox_Table_1.vpx
└── launch_jukebox.sh

/path/to/tables/Jukebox_Table_2/
├── Jukebox_Table_2.vpx
└── launch_jukebox.sh
```

**Make the script executable:**
```bash
chmod +x /path/to/tables/Jukebox_Table_1/launch_jukebox.sh
chmod +x /path/to/tables/Jukebox_Table_2/launch_jukebox.sh
```

**Update database:**
```python
from pinballux.src.database.models import DatabaseManager, Table

db = DatabaseManager()
db.initialize()

with db.get_session() as session:
    # Update Jukebox table 1
    table1 = session.query(Table).filter(
        Table.file_path.like("%Jukebox_Table_1%")
    ).first()
    if table1:
        table1.custom_launcher = "launch_jukebox.sh"

    # Update Jukebox table 2
    table2 = session.query(Table).filter(
        Table.file_path.like("%Jukebox_Table_2%")
    ).first()
    if table2:
        table2.custom_launcher = "launch_jukebox.sh"

    session.commit()
    print("Custom launchers configured for Jukebox tables")
```

## Custom Launcher Script Requirements

Your custom launcher script should:

1. **Be executable**: `chmod +x launch_script.sh`
2. **Launch the game**: Start the appropriate executable
3. **Block until exit**: The script should not return until the game exits
4. **Exit cleanly**: Return exit code 0 for normal exit

### Example Launch Script

```bash
#!/bin/bash
# launch_jukebox.sh - Custom launcher for Jukebox tables

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Navigate to the script directory
cd "$SCRIPT_DIR"

# Launch the custom Jukebox launcher
# Replace this with your actual launch command
exec /path/to/jukebox_launcher

# Alternative: If you need to run VPinballX_GL with special arguments
# exec /path/to/VPinballX_GL -EnableTrueFullscreen -Play -CustomArg "$(basename "$SCRIPT_DIR")"/*.vpx
```

## Updating Existing Tables

If you've already scanned your tables and need to add custom launchers:

```python
from pathlib import Path
from pinballux.src.database.models import DatabaseManager, Table

db = DatabaseManager()
db.initialize()

with db.get_session() as session:
    # Find all Jukebox tables
    jukebox_tables = session.query(Table).filter(
        Table.name.like("%Jukebox%")
    ).all()

    for table in jukebox_tables:
        table_dir = Path(table.file_path).parent
        launcher_path = table_dir / "launch_jukebox.sh"

        if launcher_path.exists():
            table.custom_launcher = "launch_jukebox.sh"
            print(f"Set custom launcher for: {table.name}")

    session.commit()
```

## Troubleshooting

### Custom launcher not executing

1. **Check permissions**: `ls -l /path/to/launcher.sh` should show executable bit (`-rwxr-xr-x`)
2. **Make executable**: `chmod +x /path/to/launcher.sh`
3. **Check shebang**: Script should start with `#!/bin/bash` or `#!/bin/sh`
4. **Check logs**: Look in PinballUX logs for error messages

### Script path not found

1. **Use relative paths**: `custom_launcher` should be relative to table directory (e.g., `launch_jukebox.sh`, not `/full/path/to/launch_jukebox.sh`)
2. **Verify table directory**: Make sure the table's `file_path` is correct in the database

### Script runs but game doesn't launch

1. **Check working directory**: Script runs from table directory
2. **Use absolute paths**: In your script, use absolute paths for executables
3. **Add logging**: Add `echo` statements to your script to debug
4. **Test manually**: Run the script manually from the table directory

### Script exits immediately

1. **Use `exec`**: Replace the current process instead of spawning a subprocess
2. **Wait for completion**: If spawning subprocess, use `wait` to block until it completes
3. **Check exit codes**: Make sure your script returns proper exit codes

## Example: Setting Custom Launcher Programmatically

Create a helper script to configure your Jukebox tables:

```python
#!/usr/bin/env python3
"""
configure_jukebox_launchers.py - Configure custom launchers for Jukebox tables
"""

from pathlib import Path
from pinballux.src.database.models import DatabaseManager, Table

def configure_jukebox_tables():
    """Configure custom launchers for all Jukebox tables"""
    db = DatabaseManager()
    db.initialize()

    with db.get_session() as session:
        # Find all tables with "Jukebox" in the name
        tables = session.query(Table).filter(
            Table.name.like("%Jukebox%")
        ).all()

        updated = 0
        for table in tables:
            table_dir = Path(table.file_path).parent
            launcher_script = table_dir / "launch_jukebox.sh"

            if launcher_script.exists():
                # Verify it's executable
                if not launcher_script.stat().st_mode & 0o111:
                    print(f"Warning: {launcher_script} is not executable")
                    print(f"Run: chmod +x {launcher_script}")
                    continue

                # Set custom launcher
                table.custom_launcher = "launch_jukebox.sh"
                updated += 1
                print(f"✓ Configured: {table.name}")
            else:
                print(f"✗ Launcher not found for: {table.name}")
                print(f"  Expected: {launcher_script}")

        if updated > 0:
            session.commit()
            print(f"\nSuccessfully configured {updated} table(s)")
        else:
            print("\nNo tables were updated")

if __name__ == "__main__":
    configure_jukebox_tables()
```

Save this as `configure_jukebox_launchers.py` and run:

```bash
python3 configure_jukebox_launchers.py
```

## Technical Details

### Database Schema

The `custom_launcher` field is stored in the `tables` table:

```sql
ALTER TABLE tables ADD COLUMN custom_launcher VARCHAR(500);
```

### Launch Process

When launching a table:

1. PinballUX checks if `table.custom_launcher` is set
2. If set, constructs full path: `table_directory / custom_launcher`
3. Verifies the script exists and is executable
4. Launches the script with working directory set to table directory
5. Monitors the process and tracks play time
6. Handles exit codes and cleanup

### API Usage

```python
from pinballux.src.core.vpx_launcher import LaunchManager
from pinballux.src.core.config import Config

config = Config.load()
launcher = LaunchManager(config, table_service)

# Launch with custom launcher explicitly
launcher.launch_table_by_path(
    "/path/to/table.vpx",
    options={'custom_launcher': 'launch_jukebox.sh'}
)

# Launch by ID (uses table's custom_launcher if set)
launcher.launch_table_by_id(table_id)
```
