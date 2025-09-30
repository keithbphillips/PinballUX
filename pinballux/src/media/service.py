"""
Media service for integrating media management with table database
"""

from typing import Dict, List, Optional
from pathlib import Path

from .manager import MediaManager
from ..database.service import TableService
from ..database.models import Table
from ..core.config import Config
from ..core.logger import get_logger

logger = get_logger(__name__)


class MediaService:
    """Service for managing table media integration"""

    def __init__(self, config: Config, table_service: TableService, media_root_dir: str = None):
        self.config = config
        self.table_service = table_service
        self.media_manager = MediaManager(config, media_root_dir)
        self.logger = get_logger(__name__)

    def update_table_media_paths(self, table_id: int) -> bool:
        """Update media paths for a specific table"""
        try:
            table = self.table_service.get_table_by_id(table_id)
            if not table:
                self.logger.error(f"Table not found: {table_id}")
                return False

            # Find media files for this table
            media_files = self.media_manager.find_table_media(
                table.name,
                table.manufacturer or '',
                table.year
            )

            # Update table with found media paths
            with self.table_service.db.get_session() as session:
                db_table = session.query(Table).filter(Table.id == table_id).first()
                if db_table:
                    db_table.playfield_image = media_files.get('table_image')
                    db_table.backglass_image = media_files.get('backglass_image')
                    db_table.dmd_image = media_files.get('dmd_image')
                    db_table.topper_image = media_files.get('topper_image')
                    db_table.table_video = media_files.get('table_video')

                    session.commit()
                    self.logger.info(f"Updated media paths for table: {table.name}")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to update media paths for table {table_id}: {e}")
            return False

    def update_all_table_media_paths(self) -> Dict[str, int]:
        """Update media paths for all tables in database"""
        result = {
            'updated': 0,
            'not_found': 0,
            'errors': 0
        }

        try:
            tables = self.table_service.get_all_tables(enabled_only=False)
            self.logger.info(f"Updating media paths for {len(tables)} tables")

            for table in tables:
                try:
                    if self.update_table_media_paths(table.id):
                        result['updated'] += 1
                    else:
                        result['not_found'] += 1
                except Exception as e:
                    self.logger.error(f"Error updating media for table {table.name}: {e}")
                    result['errors'] += 1

            self.logger.info(f"Media update complete: {result}")

        except Exception as e:
            self.logger.error(f"Failed to update all table media paths: {e}")
            result['errors'] += 1

        return result

    def get_table_media_info(self, table_id: int) -> Dict[str, any]:
        """Get comprehensive media information for a table"""
        try:
            table = self.table_service.get_table_by_id(table_id)
            if not table:
                return {}

            # Get current database media paths
            current_media = {
                'table_image': table.playfield_image,
                'backglass_image': table.backglass_image,
                'dmd_image': table.dmd_image,
                'topper_image': table.topper_image,
                'table_video': table.table_video
            }

            # Find available media files
            available_media = self.media_manager.find_table_media(
                table.name,
                table.manufacturer or '',
                table.year
            )

            # Validate current paths
            current_validation = self.media_manager.validate_media_paths(current_media)

            # Check what's available vs what's set
            media_status = {}
            for media_type in current_media.keys():
                media_status[media_type] = {
                    'current_path': current_media[media_type],
                    'current_exists': current_validation.get(media_type, False),
                    'available_path': available_media.get(media_type),
                    'available_exists': bool(available_media.get(media_type)),
                    'needs_update': (
                        current_media[media_type] != available_media.get(media_type) and
                        available_media.get(media_type) is not None
                    )
                }

            return {
                'table_name': table.name,
                'table_display_name': table.display_name,
                'media_status': media_status,
                'summary': {
                    'total_media_types': len(media_status),
                    'current_valid': sum(1 for status in media_status.values() if status['current_exists']),
                    'available_files': sum(1 for status in media_status.values() if status['available_exists']),
                    'needs_updates': sum(1 for status in media_status.values() if status['needs_update'])
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to get media info for table {table_id}: {e}")
            return {}

    def get_media_statistics(self) -> Dict[str, any]:
        """Get overall media statistics"""
        try:
            # Get media manager statistics
            media_stats = self.media_manager.get_media_statistics()

            # Get table count
            tables = self.table_service.get_all_tables(enabled_only=False)
            table_count = len(tables)

            # Count tables with media
            tables_with_media = 0
            for table in tables:
                if any([table.playfield_image, table.backglass_image, table.dmd_image,
                       table.topper_image, table.table_video]):
                    tables_with_media += 1

            return {
                'media_files': media_stats,
                'tables': {
                    'total_tables': table_count,
                    'tables_with_media': tables_with_media,
                    'tables_without_media': table_count - tables_with_media,
                    'media_coverage_percent': (tables_with_media / table_count * 100) if table_count > 0 else 0
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to get media statistics: {e}")
            return {}

    def find_missing_media(self) -> List[Dict[str, any]]:
        """Find tables that are missing media files"""
        missing_media = []

        try:
            tables = self.table_service.get_all_tables(enabled_only=False)

            for table in tables:
                media_info = self.get_table_media_info(table.id)
                if media_info:
                    missing_types = []
                    for media_type, status in media_info.get('media_status', {}).items():
                        if not status['current_exists'] and not status['available_exists']:
                            missing_types.append(media_type)

                    if missing_types:
                        missing_media.append({
                            'table_id': table.id,
                            'table_name': table.name,
                            'display_name': table.display_name,
                            'missing_media_types': missing_types,
                            'missing_count': len(missing_types)
                        })

        except Exception as e:
            self.logger.error(f"Failed to find missing media: {e}")

        return missing_media

    def get_orphaned_media(self) -> List[Dict[str, any]]:
        """Find media files that don't have corresponding tables"""
        orphaned_media = []

        try:
            # Get all tables
            tables = self.table_service.get_all_tables(enabled_only=False)
            table_names = set()

            for table in tables:
                # Add various name variations
                table_names.add(table.name.lower())
                if table.manufacturer and table.year:
                    table_names.add(f"{table.name} ({table.manufacturer} {table.year})".lower())

            # Scan media directory
            media_catalog = self.media_manager.scan_media_directory()

            for category, media_files in media_catalog.items():
                for media_file in media_files:
                    table_name_lower = media_file.table_name.lower()

                    # Check if this media file has a corresponding table
                    has_table = False
                    for known_name in table_names:
                        if known_name in table_name_lower or table_name_lower in known_name:
                            has_table = True
                            break

                    if not has_table:
                        orphaned_media.append({
                            'file_path': media_file.file_path,
                            'category': media_file.category,
                            'media_type': media_file.media_type,
                            'extracted_table_name': media_file.table_name,
                            'file_size': Path(media_file.file_path).stat().st_size if Path(media_file.file_path).exists() else 0
                        })

        except Exception as e:
            self.logger.error(f"Failed to find orphaned media: {e}")

        return orphaned_media

    def set_media_root_directory(self, new_root: str) -> bool:
        """Change the media root directory"""
        try:
            new_path = Path(new_root)
            if new_path.exists() and new_path.is_dir():
                self.media_manager.media_root = new_path
                self.logger.info(f"Media root directory changed to: {new_root}")
                return True
            else:
                self.logger.error(f"Invalid media root directory: {new_root}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to set media root directory: {e}")
            return False