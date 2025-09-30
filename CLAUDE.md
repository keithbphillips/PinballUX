# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Run the application
python pinballux/src/main.py

# Or run via entry point (after installation)
pinballux
```

### Development Tasks
```bash
# Install development dependencies (if testing framework added)
pip install -r requirements.txt

# Run with specific config file
PINBALLUX_CONFIG=/path/to/config.json python pinballux/src/main.py
```

## Architecture Overview

### Core Application Flow
1. **Entry Point**: `pinballux/src/main.py` - Sets up PyQt6 application, logging, and launches PinballUXApp
2. **Main App**: `core/application.py` - PinballUXApp manages the overall application lifecycle
3. **Configuration**: `core/config.py` - JSON-based config system with dataclasses for typed configurations
4. **Multi-Monitor**: `displays/monitor_manager.py` - Manages multiple display windows across monitors

### Multi-Monitor Architecture
The application is built around a **multi-monitor pinball cabinet setup**:

- **Playfield**: Main table selection interface (primary monitor)
- **Backglass**: Animated backglass artwork display
- **DMD/FullDMD**: Dot matrix display simulation
- **Topper**: Additional cabinet lighting/effects display

Each display type inherits from `BaseDisplay` and is managed by `MonitorManager`. The system automatically detects available screens and positions windows based on configuration.

### Configuration System
Configuration uses dataclasses and is stored in `~/.config/pinballux/config.json`:

- **DisplayConfig**: Monitor positions, sizes, rotations for each display type
- **VPXConfig**: Visual Pinball Standalone executable and directory paths
- **InputConfig**: Keyboard and joystick input mappings

The Config class handles loading/saving and creates sensible defaults if no config exists.

### Signal-Based Communication
The application uses PyQt6 signals for loose coupling:
- `table_selected` - When user selects a table to play
- `exit_requested` - Application shutdown requests
- `display_created/closed` - Monitor management events

## Key Design Patterns

### Display Management
- Each display type (Backglass, DMD, Topper) inherits from `BaseDisplay`
- `MonitorManager` handles creation, positioning, and lifecycle of display windows
- Displays are positioned based on `MonitorConfig` dataclass settings
- Frameless windows with black backgrounds for cabinet integration

### Configuration Architecture
- Dataclass-based typed configuration with JSON serialization
- Automatic config directory creation in user's home directory
- Graceful fallback to defaults if config is missing or corrupted
- Configuration is saved automatically on application exit

### Component Structure
- **core/**: Application lifecycle, configuration, logging
- **displays/**: Multi-monitor display management
- **ui/**: User interface components (main table selection interface)
- **database/**: Table metadata management (planned)
- **media/**: Video, audio, image handling (planned)
- **input/**: Joystick and keyboard input handling (planned)

## Development Status

This is an early-stage project. The core multi-monitor architecture and configuration system are implemented. Key areas needing implementation:

1. Main UI table selection interface (`ui/main_window.py` - referenced but not implemented)
2. Display components (`backglass_display.py`, `dmd_display.py`, `topper_display.py` - referenced but not implemented)
3. VPX table database and launching system
4. Media playback system
5. Input handling system

## Target Platform

- **Linux-specific**: Designed for Linux pinball cabinets
- **Visual Pinball Standalone**: VPX file compatibility
- **PyQt6**: Modern Qt bindings for Python
- **Multi-monitor**: Essential for pinball cabinet setups