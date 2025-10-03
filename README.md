![PinballUX](docs/PinballUX.png)

# PinballUX

A Visual Pinball frontend for Linux with multi-monitor support, inspired by PinballX.

## Features

- **Multi-Monitor Support**: Playfield, Backglass, DMD, FullDMD, and Topper displays
- **VPX Compatibility**: Works with Visual Pinball Standalone for Linux
- **Media Integration**: Video previews, table images, and audio support
- **Input Handling**: Keyboard and joystick/gamepad support
- **Resolution Scaling**: Adaptive layouts for different monitor configurations
- **Table Management**: Database-driven table organization with metadata

## Requirements

- Python 3.8+
- PyQt6
- Visual Pinball Standalone for Linux
- Linux with X11 or Wayland

## Installation

1. Clone the repository:
```bash
git clone https://github.com/keithbphillips/PinballUX.git
cd PinballUX
```

2. Install Visual Pinball Standalone for Linux:
   - Download Visual Pinball Standalone for Linux from [GitHub Releases](https://github.com/vpinball/vpinball/releases)
   - Extract the VPinball directory into the PinballUX root directory as `vpinball/`
   - The structure should look like: `PinballUX/vpinball/VPinballX_GL`
   - Place ROM files in `PinballUX/roms/` directory

3. Set up Python virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

4. Install Python dependencies:
```bash
pip install -r requirements.txt
```

5. Add your VPX table files to `pinballux/data/tables/`

6. **Scan and index your tables** (required for first-time setup):
```bash
python scan_tables.py
```

This will:
- Scan for all VPX table files in `pinballux/data/tables/`
- Extract table metadata (name, manufacturer, year, etc.)
- Find and link associated media files
- Build the table database for the frontend
- Report what was found

## Table Management

### Initial Setup

After adding your VPX table files to `pinballux/data/tables/`, you **must** run the table scanner to build the database:

```bash
python scan_tables.py
```

The scanner will display a detailed report showing:
- **New tables added** to the database
- **Media files found** for each table (videos 🎬, images 🖼️, audio 🔊)
- **Database statistics** (total tables, manufacturers, etc.)
- **Complete table listing** grouped by manufacturer

Example output:
```
📀 TABLE FILES:
   Scanned:  22 files
   New:      22 tables added
   Updated:  0 tables updated

🎬 MEDIA FILES:
   Tables:   22 tables processed
   Updated:  18 tables with media found

📊 DATABASE STATISTICS:
   Total Tables:    22
   Manufacturers:   6
```

### Adding or Removing Tables

Whenever you add new tables or remove existing ones, run the scanner again:

```bash
python scan_tables.py
```

The scanner automatically:
- **Detects and adds new tables** to the database
- **Updates existing tables** if files have changed
- **Removes deleted tables** from the database
- **Rescans media files** to find new videos, images, or audio

### Media File Detection

The scanner automatically finds media files that match your table names. For best results:

1. Place media files in the appropriate directories (see Media Files section below)
2. Name media files to **exactly match** the table name
3. Run the scanner after adding new media files

The scanner will show which tables have media with icons:
- 🎬 Table has video media
- 🖼️ Table has backglass/image media
- 🔊 Table has audio media

## Ubuntu Display Configuration

**IMPORTANT**: Before running PinballUX, you must configure your Ubuntu display settings correctly for multi-monitor support to work properly.

![Display Settings](docs/Display_Settings.png)

### Display Configuration Requirements:

1. **Primary Display**: Set your **Playfield monitor** as the Primary Display in Ubuntu Settings
2. **Horizontal Arrangement**: Arrange all displays horizontally (left-to-right)
3. **Top Alignment**: Align all displays to the top edge

PinballUX relies on Ubuntu's display configuration and screen numbering. The application will detect screens in the order Ubuntu assigns them (0, 1, 2, etc.) and position windows accordingly.

### Configuration File

Edit `~/.config/pinballux/config.json` to map each display type to the correct screen number:

```json
"displays": {
  "playfield": {
    "screen_number": 3,
    "dmd_mode": "full"
  },
  "backglass": {
    "screen_number": 2,
    "dmd_mode": "full"
  },
  "dmd": {
    "screen_number": 1,
    "dmd_mode": "native"
  }
}
```

- **screen_number**: Which physical screen (0-based index) for this display
- **dmd_mode**: `"native"` (original size) or `"full"` (scaled to screen)

Resolution changes are automatically detected on application restart.

### Audio Configuration

Control audio playback in `~/.config/pinballux/config.json`:

```json
"audio": {
  "table_audio": true
}
```

- **table_audio**: When `true`, plays table-specific audio when navigating to a table in the wheel interface. Audio files should be placed in `pinballux/data/media/audio/table/` and match the table name (e.g., `My Table.mp3`).

## Usage

Run PinballUX:
```bash
python run_pinballux.py
```

### Keyboard Controls

- **← / →** (Left/Right Arrow Keys): Navigate through the table wheel
- **Enter**: Launch selected table
- **R**: Rotate display 90° clockwise (useful for portrait/landscape orientation)
- **Escape**: Exit PinballUX

### Joystick/Controller Configuration

PinballUX includes a joystick mapping utility that configures buttons for both the frontend navigation and Visual Pinball gameplay.

#### Configuring Your Controller

Run the joystick mapper:
```bash
python map_joystick.py
```

The mapper will guide you through configuring:

**Frontend Controls:**
- Navigate wheel left/right
- Select table

**Gameplay Controls (Visual Pinball):**
- Left/Right flippers
- Plunger
- Start game
- Add credit/Menu
- Left/Right MagnaSave
- Exit table

Button mappings are saved to:
- `~/.config/pinballux/config.json` (PinballUX frontend)
- `~/.vpinball/VPinballX.ini` (Visual Pinball gameplay)

#### Example Configuration Files

The `example_configs/` directory contains reference files:

- **example_configs/gamecontrollerdb.txt**: SDL2 controller database for improved controller recognition
  - Copy to `~/.vpinball/gamecontrollerdb.txt` to help Visual Pinball correctly identify your controller

- **example_configs/VPinballX.ini**: Example Visual Pinball configuration showing sample joystick button mappings (0-based indexing)

## Media Files

PinballUX uses a structured media system where files must match the table name and be placed in the appropriate directory:

### Media Directory Structure

```
pinballux/data/media/
├── videos/
│   ├── table/          # Table gameplay videos
│   ├── backglass/      # Backglass videos
│   ├── dmd/            # DMD videos
│   ├── real_dmd/       # Real DMD capture videos
│   ├── real_dmd_color/ # Color DMD videos
│   └── topper/         # Topper videos
├── images/
│   ├── table/          # Table playfield images
│   ├── backglass/      # Backglass images
│   ├── wheel/          # Wheel images for table selection
│   └── dmd/            # DMD images
└── audio/
    ├── table/          # Table-specific audio (plays when table is highlighted)
    ├── launch/         # Table launch audio
    └── ui/             # UI sound effects
```

### Media File Naming Convention

Media files must match the table name exactly. For example, for a table named "My Favorite Table.vpx":

- **Table video**: `My Favorite Table.mp4` → `pinballux/data/media/videos/table/`
- **Backglass video**: `My Favorite Table.mp4` → `pinballux/data/media/videos/backglass/`
- **DMD video**: `My Favorite Table.mp4` → `pinballux/data/media/videos/real_dmd_color/`
- **Wheel image**: `My Favorite Table.png` → `pinballux/data/media/images/wheel/`
- **Table audio**: `My Favorite Table.mp3` → `pinballux/data/media/audio/table/`
- **Launch audio**: `My Favorite Table.mp3` → `pinballux/data/media/audio/launch/`

### Importing Media Packs

PinballUX includes a media pack importer that can automatically extract and match media files from Visual Pinball media pack ZIP files.

#### Using the Media Pack Importer

1. **Place media pack ZIP files** in the `pinballux/data/media/packs/` directory

2. **Run the importer**:
```bash
python import_media_pack.py
```

3. **Review and confirm matches**: The importer will:
   - Extract and locate the "Visual Pinball" directory inside the ZIP
   - Find Backglass Images, Table Images, and Wheel Images subdirectories
   - Match each file to tables in your database using fuzzy name matching
   - Show you the best match with a confidence score
   - Ask you to confirm (Y), skip (n), or skip all remaining (s) for each file

4. **Update the database**: After importing, run the table scanner to update media references:
```bash
python scan_tables.py
```

#### Expected Media Pack Structure

The ZIP file should contain a "Visual Pinball" directory (at any depth) with subdirectories like:
- **Backglass Images/** or **Back Glass Images/**
- **Table Images/** or **Playfield Images/**
- **Wheel Images/** or **Logo Images/**

The importer will automatically find these directories and extract matching image files (PNG, JPG, JPEG, GIF, BMP).

#### Example Import Session

```
Processing: MyMediaPack.zip
--------------------------------------------------------------------------------
✓ Found Visual Pinball directory: Media/Visual Pinball/
✓ Found media types: backglass, table, wheel

TABLE IMAGES:
----------------------------------------
  Found 15 files

  📄 The Goonies Never Say Die.png
    Best match: The Goonies Never Say Die Pinball (VPW 2021) (85% confidence)
    Import as The Goonies Never Say Die Pinball (VPW 2021)? [Y/n/s(kip all)]: y
    ✓ Imported as: The Goonies Never Say Die Pinball (VPW 2021).png
```

### Media Playback Priority

PinballUX displays media in the following priority order for each display type:

1. **Video** (if available) - preferred format: MP4, F4V
2. **Image** (if video not found) - preferred format: PNG, JPG
3. **Default content** (if no media found) - fallback display

This applies to:
- **Playfield display**: Table video → Table image → Default background
- **Backglass display**: Backglass video → Backglass image → Table name display
- **DMD display**: DMD video → DMD image → Text display

## Configuration

Configuration files are stored in `~/.config/pinballux/`:
- `config.json`: Main configuration file
- `pinballux.db`: Table database
- `logs/`: Application logs

## Project Structure

```
pinballux/
├── src/
│   ├── core/           # Core application components
│   ├── ui/             # User interface components
│   ├── database/       # Table database management
│   ├── media/          # Media handling (video, audio, images)
│   ├── input/          # Input handling (keyboard, joystick)
│   ├── displays/       # Multi-monitor display management
│   └── main.py         # Application entry point
├── config/             # Configuration files
├── data/               # Application data
│   ├── tables/         # VPX table files
│   └── media/          # Media files (images, videos, audio)
├── tests/              # Unit tests
└── docs/               # Documentation
```

## Development Status

This project is in early development. Core features are being implemented in phases:

1. ✅ Project structure and configuration system
2. 🚧 Multi-monitor architecture and display management
3. 📋 Table database and VPX launching
4. 📋 Media system and user interface
5. 📋 Input handling and themes

## Contributing

This is an open source project. Contributions are welcome!

## License

MIT License - see LICENSE file for details.