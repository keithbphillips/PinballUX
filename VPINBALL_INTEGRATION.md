# Visual Pinball Standalone Integration

## Overview

This document outlines our findings from the Visual Pinball Standalone repository and how PinballUX will integrate with it.

## Visual Pinball Standalone Architecture

### Key Findings

**Location:** `/home/keith/github/vpinball` (standalone branch)

**VPX File Format:**
- VPX files are stored in OLE Compound Document format
- Standalone uses POLE library for cross-platform .vpx file reading
- VPX contains table scripts, media, and configuration

**Linux Build Dependencies:**
- SDL2, SDL2_image, SDL2_ttf for display and input
- FreeImage for image processing
- BASS audio library for sound
- PinMAME for ROM emulation
- AltSound for enhanced audio
- DMDUtil for DMD support
- DOF (DirectOutput Framework) for cabinet hardware
- FFmpeg for video processing

**Command Line Interface:**
- Standalone version runs from command line
- Takes VPX file path as parameter
- Supports various display and audio options

## Integration Points for PinballUX

### 1. VPX File Parsing
- **Need:** Extract metadata from VPX files for our database
- **Solution:** Use Python OLE parsing libraries or call VP standalone with info-only mode
- **Files to Study:** `standalone/PoleStorage.cpp`, `standalone/PoleStream.cpp`

### 2. Table Launching
- **Command:** `vpinball_standalone [options] table.vpx`
- **Multi-Monitor:** VP Standalone supports multiple displays natively
- **Process Management:** Launch VP as subprocess, monitor for exit

### 3. DMD Integration
- **VP DMD Output:** Standalone has built-in DMD support
- **Our DMD Display:** Can either:
  - Mirror VP's DMD output
  - Use VP's DMD data stream
  - Run our own DMD simulation alongside

### 4. Media Assets
- **Table Images:** Extract from VPX or maintain separate media folder
- **Backglass Images:** VP can export these
- **Video Previews:** Capture from gameplay or use existing library

### 5. Configuration Sync
- **VP Settings:** Located in XML config files (ENABLE_INI mode)
- **Display Setup:** Coordinate our multi-monitor setup with VP's
- **Input Mapping:** Ensure our controls pass through to VP

## Implementation Strategy

### Phase 2 - Core Pinball Functionality

1. **VPX File Scanner:**
   ```python
   # Scan directory for .vpx files
   # Extract basic metadata (name, manufacturer, year)
   # Store in SQLite database
   ```

2. **VP Standalone Launcher:**
   ```python
   # subprocess.run(['vpinball_standalone', '--fullscreen', table_path])
   # Monitor process for exit/crash
   # Handle cleanup
   ```

3. **Media Management:**
   ```python
   # Organize table media in structured folders
   # /media/tables/[table_name]/
   #   - playfield.jpg
   #   - backglass.jpg
   #   - preview.mp4
   ```

### Dependencies to Install

For VP Standalone building (if needed):
```bash
# Build dependencies
sudo apt install build-essential cmake
sudo apt install libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev
sudo apt install libfreeimage-dev ffmpeg-dev
```

For PinballUX VPX parsing:
```bash
pip install olefile  # For VPX file parsing
pip install pillow   # For image processing
```

## Testing Strategy

1. **Get VP Standalone Binary:**
   - Build from source or find Linux releases
   - Test with sample VPX files

2. **VPX Sample Files:**
   - Download free VPX tables for testing
   - Test media extraction and launching

3. **Multi-Monitor Testing:**
   - Configure VP for multi-display
   - Test coordination with PinballUX displays

## File Locations

- **VP Standalone Source:** `/home/keith/github/vpinball/`
- **Linux Build Scripts:** `/home/keith/github/vpinball/standalone/linux-x64/`
- **Build Dependencies:** See `external.sh` script
- **Main VP Code:** `main.cpp`, `vpinball.cpp`

## Next Steps

1. **Build VP Standalone** for testing
2. **Create VPX parser** for metadata extraction
3. **Implement table launcher** with process management
4. **Test multi-monitor coordination** between PinballUX and VP