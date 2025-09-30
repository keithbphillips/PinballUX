"""
Media management system for PinballUX
Handles images, videos, and audio files for tables
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from ..core.config import Config
from ..core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MediaFile:
    """Represents a media file"""
    file_path: str
    media_type: str  # image, video, audio
    category: str    # table, backglass, dmd, topper, wheel, launch
    table_name: str
    exists: bool = True


class MediaManager:
    """Manages media files for pinball tables"""

    def __init__(self, config: Config, media_root_dir: str = None):
        self.config = config
        self.logger = get_logger(__name__)

        # Set media root directory
        if media_root_dir:
            self.media_root = Path(media_root_dir)
        else:
            self.media_root = Path(config.vpx.media_directory) if config.vpx.media_directory else Path.cwd() / "Media"

        # Media directory structure (now flatter in data/media)
        self.media_categories = {
            'table_images': 'images/table',
            'table_videos': 'videos/table',
            'backglass_images': 'images/backglass',
            'backglass_videos': 'videos/backglass',
            'dmd_images': 'images/dmd',
            'dmd_videos': 'videos/dmd',
            'topper_images': 'images/topper',
            'topper_videos': 'videos/topper',
            'wheel_images': 'images/wheel',
            'table_audio': 'audio/table',
            'launch_audio': 'audio/launch',
            'fulldmd_videos': 'videos/fulldmd',
            'real_dmd_images': 'images/real_dmd',
            'real_dmd_videos': 'videos/real_dmd',
            'real_dmd_color_images': 'images/real_dmd_color',
            'real_dmd_color_videos': 'videos/real_dmd_color',
            'default_images': 'images/default',
            'default_videos': 'videos/default'
        }

        # Supported file extensions
        self.image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'}
        self.video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm', '.f4v', '.flv'}
        self.audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
        self.backglass_extensions = {'.directb2s', '.directB2S'}  # DirectB2S backglass files

        self.logger.info(f"Media manager initialized with root: {self.media_root}")

    def find_table_media(self, table_name: str, manufacturer: str = '', year: int = None) -> Dict[str, Optional[str]]:
        """Find all media files for a specific table"""
        media_files = {
            'table_image': None,
            'table_video': None,
            'backglass_image': None,
            'backglass_video': None,
            'dmd_image': None,
            'dmd_video': None,
            'topper_image': None,
            'topper_video': None,
            'wheel_image': None,
            'table_audio': None,
            'launch_audio': None
        }

        # Generate possible table name variations
        name_variations = self._generate_name_variations(table_name, manufacturer, year)

        # Search for each media type
        for media_key, category_dir in self.media_categories.items():
            category_path = self.media_root / category_dir

            if not category_path.exists():
                continue

            # Determine file type from category
            if 'images' in category_dir.lower() or 'image' in category_dir.lower():
                # For backglass images, also include directb2s files
                if 'backglass' in category_dir.lower():
                    extensions = self.image_extensions | self.backglass_extensions
                else:
                    extensions = self.image_extensions
                media_type = 'image'
            elif 'videos' in category_dir.lower() or 'video' in category_dir.lower():
                extensions = self.video_extensions
                media_type = 'video'
            elif 'audio' in category_dir.lower():
                extensions = self.audio_extensions
                media_type = 'audio'
            else:
                continue

            # Find matching file
            found_file = self._find_matching_file(category_path, name_variations, extensions)
            if found_file:
                # Map to simplified key names
                if 'table' in media_key and media_type == 'image':
                    media_files['table_image'] = str(found_file)
                elif 'table' in media_key and media_type == 'video':
                    media_files['table_video'] = str(found_file)
                elif 'backglass' in media_key and media_type == 'image':
                    media_files['backglass_image'] = str(found_file)
                elif 'backglass' in media_key and media_type == 'video':
                    media_files['backglass_video'] = str(found_file)
                elif 'dmd' in media_key and media_type == 'image':
                    media_files['dmd_image'] = str(found_file)
                elif 'dmd' in media_key and media_type == 'video':
                    media_files['dmd_video'] = str(found_file)
                elif 'topper' in media_key and media_type == 'image':
                    media_files['topper_image'] = str(found_file)
                elif 'topper' in media_key and media_type == 'video':
                    media_files['topper_video'] = str(found_file)
                elif 'wheel' in media_key:
                    media_files['wheel_image'] = str(found_file)
                elif 'table_audio' in media_key:
                    media_files['table_audio'] = str(found_file)
                elif 'launch_audio' in media_key:
                    media_files['launch_audio'] = str(found_file)

        return media_files

    def _generate_name_variations(self, table_name: str, manufacturer: str = '', year: int = None) -> List[str]:
        """Generate possible filename variations for a table"""
        variations = []

        # Clean table name
        clean_name = self._clean_filename(table_name)
        variations.append(clean_name)

        # Add manufacturer and year variations
        if manufacturer and year:
            # "TableName (Manufacturer Year)"
            variations.append(f"{clean_name} ({manufacturer} {year})")
            # "TableName (Manufacturer Year).ext"
            variations.append(f"{clean_name} ({self._clean_filename(manufacturer)} {year})")

        if manufacturer:
            # "TableName (Manufacturer)"
            variations.append(f"{clean_name} ({manufacturer})")
            variations.append(f"{clean_name} ({self._clean_filename(manufacturer)})")

        if year:
            # "TableName (Year)"
            variations.append(f"{clean_name} ({year})")

        # Add variations with different separators
        for variation in variations.copy():
            # Replace spaces with underscores
            variations.append(variation.replace(' ', '_'))
            # Replace spaces with dots
            variations.append(variation.replace(' ', '.'))
            # Replace spaces with dashes
            variations.append(variation.replace(' ', '-'))

        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for variation in variations:
            if variation not in seen:
                seen.add(variation)
                unique_variations.append(variation)

        self.logger.debug(f"Generated {len(unique_variations)} name variations for '{table_name}'")
        return unique_variations

    def _clean_filename(self, name: str) -> str:
        """Clean a name for use in filenames"""
        # Remove or replace problematic characters
        cleaned = re.sub(r'[^\w\s\-_\(\)]+', '', name)
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _find_matching_file(self, directory: Path, name_variations: List[str], extensions: Set[str]) -> Optional[Path]:
        """Find a file that matches one of the name variations"""
        if not directory.exists():
            return None

        try:
            # Get all files in directory
            files = [f for f in directory.iterdir() if f.is_file()]

            # Try exact matches first
            for variation in name_variations:
                for ext in extensions:
                    filename = variation + ext
                    file_path = directory / filename
                    if file_path.exists():
                        self.logger.debug(f"Found exact match: {file_path}")
                        return file_path

            # Try case-insensitive matches
            files_lower = {f.name.lower(): f for f in files}

            for variation in name_variations:
                for ext in extensions:
                    filename_lower = (variation + ext).lower()
                    if filename_lower in files_lower:
                        found_file = files_lower[filename_lower]
                        self.logger.debug(f"Found case-insensitive match: {found_file}")
                        return found_file

            # Try partial matches (filename contains variation)
            for variation in name_variations:
                variation_lower = variation.lower()
                for file in files:
                    if file.suffix.lower() in {ext.lower() for ext in extensions}:
                        if variation_lower in file.stem.lower():
                            self.logger.debug(f"Found partial match: {file}")
                            return file

        except Exception as e:
            self.logger.error(f"Error searching directory {directory}: {e}")

        return None

    def scan_media_directory(self) -> Dict[str, List[MediaFile]]:
        """Scan the media directory and catalog all files"""
        media_catalog = {}

        if not self.media_root.exists():
            self.logger.warning(f"Media directory not found: {self.media_root}")
            return media_catalog

        for category_key, category_dir in self.media_categories.items():
            category_path = self.media_root / category_dir
            if not category_path.exists():
                continue

            media_files = []

            try:
                for file_path in category_path.iterdir():
                    if not file_path.is_file():
                        continue

                    # Determine media type
                    ext = file_path.suffix.lower()
                    if ext in self.image_extensions:
                        media_type = 'image'
                    elif ext in self.video_extensions:
                        media_type = 'video'
                    elif ext in self.audio_extensions:
                        media_type = 'audio'
                    elif ext in self.backglass_extensions:
                        media_type = 'backglass'  # Special type for directb2s files
                    else:
                        continue

                    # Extract table name from filename
                    table_name = self._extract_table_name_from_filename(file_path.stem)

                    media_file = MediaFile(
                        file_path=str(file_path),
                        media_type=media_type,
                        category=category_key,
                        table_name=table_name,
                        exists=True
                    )

                    media_files.append(media_file)

                media_catalog[category_key] = media_files
                self.logger.info(f"Found {len(media_files)} files in {category_dir}")

            except Exception as e:
                self.logger.error(f"Error scanning {category_path}: {e}")

        return media_catalog

    def _extract_table_name_from_filename(self, filename: str) -> str:
        """Extract table name from a media filename"""
        # Remove common patterns like "(Manufacturer Year)"
        # Pattern: "TableName (Manufacturer Year)"
        match = re.match(r'^(.+?)\s*\([^)]*\d{4}[^)]*\).*$', filename)
        if match:
            return match.group(1).strip()

        # Pattern: "TableName (Manufacturer)"
        match = re.match(r'^(.+?)\s*\([^)]*\).*$', filename)
        if match:
            return match.group(1).strip()

        # Just return the filename as-is if no pattern matches
        return filename

    def get_media_statistics(self) -> Dict[str, int]:
        """Get statistics about available media files"""
        stats = {}
        catalog = self.scan_media_directory()

        for category, files in catalog.items():
            stats[category] = len(files)

        total_files = sum(stats.values())
        stats['total_files'] = total_files

        return stats

    def validate_media_paths(self, media_dict: Dict[str, Optional[str]]) -> Dict[str, bool]:
        """Validate that media file paths exist"""
        validation_results = {}

        for media_type, file_path in media_dict.items():
            if file_path:
                validation_results[media_type] = Path(file_path).exists()
            else:
                validation_results[media_type] = False

        return validation_results

    def get_default_media(self, media_type: str) -> Optional[str]:
        """Get default media file for a specific type"""
        default_dir = self.media_root / "images" / "default"

        if media_type == 'table_image' and default_dir.exists():
            # Look for default table image
            for ext in self.image_extensions:
                default_file = default_dir / f"default{ext}"
                if default_file.exists():
                    return str(default_file)

        # Could add more default media types here
        return None

    def copy_media_to_structure(self, source_dir: str, dry_run: bool = True) -> Dict[str, int]:
        """Copy media files from a source directory to PinballX structure"""
        # This would be used to organize existing media files
        # Implementation would copy files to appropriate subdirectories
        # For now, just return a placeholder
        return {'copied_files': 0, 'errors': 0}