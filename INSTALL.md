# PinballUX Installation Guide

## Quick Install (Ubuntu/Debian)

### Option 1: Install from .deb Package (Recommended)

1. **Download the latest package:**

   Visit the [Releases page](https://github.com/keithbphillips/PinballUX/releases) and download `pinballux_0.1.0-1_all.deb`

   Or use wget:
   ```bash
   wget https://github.com/keithbphillips/PinballUX/releases/latest/download/pinballux_0.1.0-1_all.deb
   ```

2. **Install the package:**
   ```bash
   sudo dpkg -i pinballux_0.1.0-1_all.deb

   # If dependencies are missing, install them:
   sudo apt install -f
   ```

3. Run the Setup GUI to configure PinballUX:
   ```bash
   pinballux-setup
   ```
   - Configure your displays (playfield, backglass, DMD, etc.)
   - Download and install VPinball automatically
   - Set up keyboard and joystick controls
   - Configure paths

4. Run Table Manager to scan tables and download media:
   ```bash
   pinballux-manager
   ```
   - Place your VPX tables in `/opt/pinballux/pinballux/data/tables/`
   - Scan tables automatically on startup
   - Download media from ftp.gameex.com

5. Launch PinballUX:
   ```bash
   pinballux
   ```

### Option 2: Install from Source

See [README.md](README.md) for detailed source installation instructions.

## Post-Installation

After installation, you can access PinballUX from:

- **Command line**: `pinballux`, `pinballux-setup`, `pinballux-manager`
- **Application menu**: Look for "PinballUX" in your Games category
- **Desktop actions**: Right-click the PinballUX icon to access Setup or Table Manager

## File Locations

- **Application**: `/opt/pinballux/`
- **Configuration**: `~/.config/pinballux/config.json`
- **Database**: `~/.config/pinballux/pinballux.db`
- **Tables**: `/opt/pinballux/pinballux/data/tables/`
- **Media**: `/opt/pinballux/pinballux/data/media/`
- **ROMs**: `/opt/pinballux/pinballux/data/roms/`
- **VPinball**: `/opt/pinballux/vpinball/` (after download via Setup GUI)

## Updating

To update to a new version:

```bash
# Download the new .deb package
sudo dpkg -i pinballux_0.2.0-1_all.deb
```

Your configuration and data will be preserved.

## Uninstalling

```bash
sudo apt remove pinballux
```

This will remove the application but preserve your configuration in `~/.config/pinballux/`.

To completely remove including configuration:

```bash
sudo apt purge pinballux
rm -rf ~/.config/pinballux
```

## Troubleshooting

### Missing Dependencies

If you see dependency errors:

```bash
sudo apt install -f
```

### Permission Issues

If you can't write to data directories:

```bash
sudo chmod -R 777 /opt/pinballux/pinballux/data
```

### Reset Configuration

To reset to default configuration:

```bash
rm ~/.config/pinballux/config.json
pinballux-setup
```

## System Requirements

- Ubuntu 24.04 LTS or later (recommended)
- Python 3.8 or later
- PyQt6
- 4GB RAM minimum
- Graphics card with multi-monitor support
- X11 or Wayland display server

## Getting Help

- [GitHub Issues](https://github.com/keithbphillips/PinballUX/issues)
- [README.md](README.md) - Full documentation
- [debian/README.build](debian/README.build) - Package building instructions
