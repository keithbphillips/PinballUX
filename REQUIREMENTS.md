# PinballUX - Visual Pinball Frontend for Linux

## Project Overview
A Visual Pinball frontend similar to PinballX, designed specifically for Linux systems with multi-monitor pinball cabinet setups.

## Core Requirements

### Technology Stack
- **Language:** Python 3.8+
- **GUI Framework:** PyQt6
- **Target Platform:** Linux
- **Visual Pinball:** Standalone for Linux with VPX compatibility

### Essential Features

#### Multi-Monitor Support
- **Playfield Display:** Main table view (primary monitor)
- **Backglass Display:** Animated backglass artwork
- **DMD Display:** Dot matrix display simulation
- **FullDMD Display:** Extended DMD functionality
- **Topper Display:** Additional cabinet lighting/effects
- **Resolution Scaling:** Adaptive layouts for different monitor sizes and orientations

#### Table Management
- **VPX File Support:** Visual Pinball Standalone table launching
- **Database Management:** Table metadata, descriptions, ratings
- **Media Integration:** Table images, videos, audio per table
- **High Score Tracking:** Integration with scoring systems

#### Media System
- **Video Playback:** Table preview videos, attract mode
- **Audio System:** Sounds, music, voice announcements
- **Image Support:** Table artwork, backglass images
- **Preview System:** Real-time table media display

#### Input Handling
- **Joystick Support:** Gamepad/arcade controller input
- **Keyboard Support:** Configurable key mappings
- **Navigation:** Menu navigation across all displays
- **Cabinet Controls:** Flipper buttons, nudge, start buttons

#### User Interface
- **Table Browser:** Grid/list view with filtering
- **Search Functionality:** By manufacturer, year, rating, genre
- **Configuration System:** Monitor layouts, paths, input mappings
- **Theme System:** Customizable appearance across all displays

### Secondary Features
- **Statistics Tracking:** Play time, launch counts
- **Backup/Restore:** Configuration and database backup
- **Remote Access:** Network-based control options
- **Plugin System:** Extensible architecture for additional features

## Technical Specifications

### Performance Requirements
- **Multi-core CPU:** Optimized for quad-core systems
- **Memory:** Efficient handling of large media collections
- **Storage:** Fast access to table files and media
- **Graphics:** Hardware acceleration for video playback

### File Format Support
- **Tables:** .vpx files (Visual Pinball X format)
- **Videos:** MP4, AVI with hardware acceleration
- **Images:** PNG, JPG, GIF for artwork
- **Audio:** MP3, WAV, OGG for sounds and music

### Monitor Configuration
- **Flexible Layout:** Support for various cabinet configurations
- **Display Positioning:** Precise monitor placement and sizing
- **Orientation Support:** Portrait/landscape mixed setups
- **Bezel Compensation:** Adjustments for physical cabinet bezels

## Development Phases

1. **Core Architecture:** Multi-monitor framework and basic UI
2. **Table Management:** Database and VPX launching
3. **Media Integration:** Video, audio, and image systems
4. **Input System:** Controller and keyboard handling
5. **Advanced Features:** Themes, statistics, and configuration
6. **Polish & Testing:** Performance optimization and bug fixes