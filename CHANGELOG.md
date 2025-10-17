# Changelog

All notable changes to PinballUX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.6] - 2025-10-17

### Fixed
- Fixed media preview refresh issue in Table Manager where video previews would not properly update when switching between different media types (video/image/audio)
- Resolved native video overlay cleanup issue causing ghost videos to appear behind the application window
- QVideoWidget instances are now properly destroyed and recreated for all media type transitions

### Improved
- Log window in Table Manager now auto-scrolls to bottom to always show the latest entries

## [0.2.5] - Previous Release

### Added
- Initial table manager functionality
- Media download from FTP
- CSV database import
- Media pack import support
