"""
Database service for managing table data
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from .models import DatabaseManager, Table, Category, TableCategory, PlaySession
from .vpx_parser import TableScanner
from ..core.logger import get_logger
from ..media.manager import MediaManager

logger = get_logger(__name__)


class TableService:
    """Service for managing table data and operations"""

    def __init__(self, database_manager: DatabaseManager, media_manager: MediaManager = None):
        self.db = database_manager
        self.scanner = TableScanner()
        self.media_manager = media_manager
        self.logger = get_logger(__name__)

    def scan_and_import_tables(self, directory: str, recursive: bool = True) -> Dict[str, int]:
        """Scan directory for VPX files and import them to database"""
        result = {
            'scanned': 0,
            'new': 0,
            'updated': 0,
            'errors': 0
        }

        try:
            self.logger.info(f"Scanning directory for VPX files: {directory}")
            table_data_list = self.scanner.scan_directory(directory, recursive)
            result['scanned'] = len(table_data_list)

            with self.db.get_session() as session:
                for table_data in table_data_list:
                    try:
                        # Check if table already exists
                        existing_table = session.query(Table).filter(
                            Table.file_path == table_data['file_path']
                        ).first()

                        if existing_table:
                            # Update existing table
                            updated = self._update_table_from_data(existing_table, table_data)
                            # Update media paths
                            if self.media_manager:
                                media_updated = self._update_table_media(existing_table)
                                updated = updated or media_updated
                            if updated:
                                result['updated'] += 1
                                self.logger.debug(f"Updated table: {table_data['name']}")
                        else:
                            # Create new table
                            new_table = self._create_table_from_data(table_data)
                            session.add(new_table)
                            # Find and assign media files
                            if self.media_manager:
                                self._update_table_media(new_table)
                            result['new'] += 1
                            self.logger.debug(f"Added new table: {table_data['name']}")

                    except Exception as e:
                        self.logger.error(f"Failed to import table {table_data.get('name', 'Unknown')}: {e}")
                        result['errors'] += 1

                session.commit()

            self.logger.info(f"Import complete: {result['new']} new, {result['updated']} updated, {result['errors']} errors")

        except Exception as e:
            self.logger.error(f"Failed to scan and import tables: {e}")
            result['errors'] += 1

        return result

    def _create_table_from_data(self, table_data: Dict[str, Any]) -> Table:
        """Create a Table object from parsed VPX data"""
        return Table(
            name=table_data.get('name', 'Unknown Table'),
            description=table_data.get('description', ''),
            manufacturer=table_data.get('manufacturer', ''),
            year=table_data.get('year'),
            type=table_data.get('type', 'SS'),
            file_path=table_data['file_path'],
            file_size=table_data.get('file_size', 0),
            file_modified=table_data.get('file_modified', datetime.utcnow()),
            vpx_version=table_data.get('vpx_version', ''),
            table_version=table_data.get('table_version', ''),
            author=table_data.get('author', ''),
            rom_name=table_data.get('rom_name', ''),
            players=table_data.get('players', 1),
            working=table_data.get('working', True),
            enabled=table_data.get('enabled', True),
            rating=0.0,
            play_count=0,
            total_play_time=0,
            favorite=False
        )

    def _update_table_media(self, table: Table) -> bool:
        """Update table media paths using MediaManager"""
        if not self.media_manager:
            return False

        try:
            # Find media files for this table
            media_files = self.media_manager.find_table_media(
                table.name,
                table.manufacturer or '',
                table.year
            )

            updated = False

            # Update media paths if found
            if media_files.get('table_image') and table.playfield_image != media_files['table_image']:
                table.playfield_image = media_files['table_image']
                updated = True

            if media_files.get('table_video') and table.table_video != media_files['table_video']:
                table.table_video = media_files['table_video']
                updated = True

            if media_files.get('backglass_image') and table.backglass_image != media_files['backglass_image']:
                table.backglass_image = media_files['backglass_image']
                updated = True

            if media_files.get('backglass_video') and table.backglass_video != media_files['backglass_video']:
                table.backglass_video = media_files['backglass_video']
                updated = True

            if media_files.get('dmd_image') and table.dmd_image != media_files['dmd_image']:
                table.dmd_image = media_files['dmd_image']
                updated = True

            if media_files.get('dmd_video') and table.dmd_video != media_files['dmd_video']:
                table.dmd_video = media_files['dmd_video']
                updated = True

            if media_files.get('topper_image') and table.topper_image != media_files['topper_image']:
                table.topper_image = media_files['topper_image']
                updated = True

            if media_files.get('topper_video') and table.topper_video != media_files['topper_video']:
                table.topper_video = media_files['topper_video']
                updated = True

            if media_files.get('wheel_image') and table.wheel_image != media_files['wheel_image']:
                table.wheel_image = media_files['wheel_image']
                updated = True

            if media_files.get('table_audio') and table.table_audio != media_files['table_audio']:
                table.table_audio = media_files['table_audio']
                updated = True

            if media_files.get('launch_audio') and table.launch_audio != media_files['launch_audio']:
                table.launch_audio = media_files['launch_audio']
                updated = True

            if updated:
                table.updated_at = datetime.utcnow()
                self.logger.debug(f"Updated media paths for table: {table.name}")

            return updated

        except Exception as e:
            self.logger.error(f"Failed to update media for table {table.name}: {e}")
            return False

    def _update_table_from_data(self, table: Table, table_data: Dict[str, Any]) -> bool:
        """Update existing table with new data, returns True if changes were made"""
        updated = False

        # Update file information
        if table.file_size != table_data.get('file_size', 0):
            table.file_size = table_data.get('file_size', 0)
            updated = True

        if table.file_modified != table_data.get('file_modified'):
            table.file_modified = table_data.get('file_modified', datetime.utcnow())
            updated = True

        # Update metadata if empty or different
        fields_to_update = [
            'name', 'description', 'manufacturer', 'year', 'type',
            'vpx_version', 'table_version', 'author', 'rom_name', 'players'
        ]

        for field in fields_to_update:
            new_value = table_data.get(field)
            current_value = getattr(table, field)

            # Update if current value is empty/None or if new value is different and not empty
            if (not current_value and new_value) or (new_value and new_value != current_value):
                setattr(table, field, new_value)
                updated = True

        # Update working status
        if table.working != table_data.get('working', True):
            table.working = table_data.get('working', True)
            updated = True

        if updated:
            table.updated_at = datetime.utcnow()

        return updated

    def get_all_tables(self, enabled_only: bool = True) -> List[Table]:
        """Get all tables from database"""
        return self.db.get_all_tables(enabled_only)

    def search_tables(self, search_term: str = '', manufacturer: str = None) -> List[Table]:
        """Search tables in database"""
        return self.db.search_tables(search_term, manufacturer)

    def get_table_by_id(self, table_id: int) -> Optional[Table]:
        """Get table by ID"""
        try:
            with self.db.get_session() as session:
                return session.query(Table).filter(Table.id == table_id).first()
        except Exception as e:
            self.logger.error(f"Failed to get table by ID {table_id}: {e}")
            return None

    def get_table_by_path(self, file_path: str) -> Optional[Table]:
        """Get table by file path"""
        return self.db.get_table_by_path(file_path)

    def update_table_rating(self, table_id: int, rating: float) -> bool:
        """Update table rating"""
        try:
            with self.db.get_session() as session:
                table = session.query(Table).filter(Table.id == table_id).first()
                if table:
                    table.rating = max(0.0, min(5.0, rating))  # Clamp between 0-5
                    table.updated_at = datetime.utcnow()
                    session.commit()
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Failed to update table rating: {e}")
            return False

    def toggle_table_favorite(self, table_id: int) -> bool:
        """Toggle table favorite status"""
        try:
            with self.db.get_session() as session:
                table = session.query(Table).filter(Table.id == table_id).first()
                if table:
                    table.favorite = not table.favorite
                    table.updated_at = datetime.utcnow()
                    session.commit()
                    return table.favorite
                return False
        except Exception as e:
            self.logger.error(f"Failed to toggle table favorite: {e}")
            return False

    def record_table_play(self, table_id: int, duration_seconds: int, score: int = None) -> bool:
        """Record a play session for a table"""
        try:
            self.db.record_play_session(table_id, duration_seconds, score)
            return True
        except Exception as e:
            self.logger.error(f"Failed to record table play: {e}")
            return False

    def get_recently_played_tables(self, limit: int = 10) -> List[Table]:
        """Get recently played tables"""
        try:
            with self.db.get_session() as session:
                return session.query(Table).filter(
                    Table.last_played.isnot(None),
                    Table.enabled == True
                ).order_by(Table.last_played.desc()).limit(limit).all()
        except Exception as e:
            self.logger.error(f"Failed to get recently played tables: {e}")
            return []

    def get_favorite_tables(self) -> List[Table]:
        """Get favorite tables"""
        try:
            with self.db.get_session() as session:
                return session.query(Table).filter(
                    Table.favorite == True,
                    Table.enabled == True
                ).order_by(Table.name).all()
        except Exception as e:
            self.logger.error(f"Failed to get favorite tables: {e}")
            return []

    def get_manufacturers(self) -> List[str]:
        """Get list of all manufacturers"""
        try:
            with self.db.get_session() as session:
                result = session.query(Table.manufacturer).filter(
                    Table.manufacturer.isnot(None),
                    Table.manufacturer != '',
                    Table.enabled == True
                ).distinct().order_by(Table.manufacturer).all()
                return [r[0] for r in result]
        except Exception as e:
            self.logger.error(f"Failed to get manufacturers: {e}")
            return []

    def get_table_statistics(self) -> Dict[str, Any]:
        """Get overall table statistics"""
        try:
            with self.db.get_session() as session:
                total_tables = session.query(Table).filter(Table.enabled == True).count()
                total_plays = session.query(PlaySession).count()
                total_play_time = session.query(Table).with_entities(
                    session.query(Table.total_play_time).label('total')
                ).scalar() or 0

                manufacturers = self.get_manufacturers()

                return {
                    'total_tables': total_tables,
                    'total_plays': total_plays,
                    'total_play_time_hours': total_play_time / 3600.0,
                    'manufacturers_count': len(manufacturers),
                    'manufacturers': manufacturers
                }
        except Exception as e:
            self.logger.error(f"Failed to get table statistics: {e}")
            return {
                'total_tables': 0,
                'total_plays': 0,
                'total_play_time_hours': 0.0,
                'manufacturers_count': 0,
                'manufacturers': []
            }

    def validate_table_files(self) -> Dict[str, List[str]]:
        """Validate that all table files still exist"""
        result = {
            'valid': [],
            'missing': [],
            'inaccessible': []
        }

        try:
            tables = self.get_all_tables(enabled_only=False)

            for table in tables:
                file_path = Path(table.file_path)

                if not file_path.exists():
                    result['missing'].append(table.file_path)
                elif not file_path.is_file():
                    result['inaccessible'].append(table.file_path)
                else:
                    result['valid'].append(table.file_path)

        except Exception as e:
            self.logger.error(f"Failed to validate table files: {e}")

        return result

    def rescan_table(self, table_id: int) -> bool:
        """Rescan a single table file and update metadata"""
        try:
            with self.db.get_session() as session:
                table = session.query(Table).filter(Table.id == table_id).first()
                if not table:
                    return False

                # Rescan the file
                new_data = self.scanner.scan_file(table.file_path)
                if new_data:
                    # Update the table
                    updated = self._update_table_from_data(table, new_data)
                    if updated:
                        session.commit()
                        self.logger.info(f"Rescanned and updated table: {table.name}")
                    return True
                else:
                    self.logger.error(f"Failed to rescan table file: {table.file_path}")
                    return False

        except Exception as e:
            self.logger.error(f"Failed to rescan table {table_id}: {e}")
            return False

    def rescan_all_tables(self) -> Dict[str, int]:
        """Rescan all existing tables and update their metadata"""
        result = {
            'total': 0,
            'updated': 0,
            'errors': 0,
            'missing': 0
        }

        try:
            tables = self.get_all_tables(enabled_only=False)
            result['total'] = len(tables)

            with self.db.get_session() as session:
                for table in tables:
                    try:
                        # Check if file still exists
                        if not Path(table.file_path).exists():
                            result['missing'] += 1
                            self.logger.warning(f"Table file missing: {table.file_path}")
                            continue

                        # Rescan the file
                        new_data = self.scanner.scan_file(table.file_path)
                        if new_data:
                            # Get the table from this session
                            db_table = session.query(Table).filter(Table.id == table.id).first()
                            if db_table:
                                updated = self._update_table_from_data(db_table, new_data)
                                if updated:
                                    result['updated'] += 1
                                    self.logger.debug(f"Updated table: {table.name}")
                        else:
                            result['errors'] += 1
                            self.logger.error(f"Failed to rescan table: {table.file_path}")

                    except Exception as e:
                        result['errors'] += 1
                        self.logger.error(f"Error rescanning table {table.name}: {e}")

                session.commit()

            self.logger.info(f"Rescan complete: {result['updated']} updated, {result['missing']} missing, {result['errors']} errors")

        except Exception as e:
            self.logger.error(f"Failed to rescan all tables: {e}")
            result['errors'] += 1

        return result

    def update_database_for_renamed_files(self, directory: str) -> Dict[str, Any]:
        """Update database to handle renamed table files"""
        result = {
            'matched': 0,
            'orphaned': 0,
            'new_files': 0,
            'errors': 0,
            'renamed_tables': []
        }

        try:
            # Get current files in directory
            current_files = set()
            directory_path = Path(directory)
            if directory_path.exists():
                for file_path in directory_path.glob("*.vpx"):
                    current_files.add(str(file_path.resolve()))

            # Get tables from database
            database_tables = self.get_all_tables(enabled_only=False)
            database_file_paths = {table.file_path: table for table in database_tables}

            # Find matches and orphans
            matched_files = set()
            orphaned_tables = []

            # Check which database entries still have valid files
            for db_path, table in database_file_paths.items():
                if db_path in current_files:
                    matched_files.add(db_path)
                    result['matched'] += 1
                else:
                    orphaned_tables.append(table)
                    result['orphaned'] += 1

            # Find completely new files
            new_files = current_files - matched_files
            result['new_files'] = len(new_files)

            self.logger.info(f"Found {result['matched']} matched, {result['orphaned']} orphaned, {result['new_files']} new files")

            # Try to match orphaned tables with new files by metadata
            with self.db.get_session() as session:
                for orphaned_table in orphaned_tables:
                    best_match = self._find_best_file_match(orphaned_table, new_files)
                    if best_match:
                        # Update the table's file path
                        db_table = session.query(Table).filter(Table.id == orphaned_table.id).first()
                        if db_table:
                            old_path = db_table.file_path
                            db_table.file_path = best_match
                            db_table.updated_at = datetime.utcnow()

                            # Rescan the file to update metadata
                            new_data = self.scanner.scan_file(best_match)
                            if new_data:
                                self._update_table_from_data(db_table, new_data)

                            result['renamed_tables'].append({
                                'table_name': db_table.name,
                                'old_path': old_path,
                                'new_path': best_match
                            })

                            new_files.remove(best_match)
                            self.logger.info(f"Matched renamed table: {db_table.name} -> {Path(best_match).name}")

                session.commit()

            # Import any remaining new files
            if new_files:
                for new_file in new_files:
                    try:
                        new_data = self.scanner.scan_file(new_file)
                        if new_data:
                            new_table = self._create_table_from_data(new_data)
                            with self.db.get_session() as session:
                                session.add(new_table)
                                session.commit()
                            self.logger.info(f"Added new table: {new_data['name']}")
                    except Exception as e:
                        result['errors'] += 1
                        self.logger.error(f"Failed to import new file {new_file}: {e}")

        except Exception as e:
            self.logger.error(f"Failed to update database for renamed files: {e}")
            result['errors'] += 1

        return result

    def _find_best_file_match(self, orphaned_table: Table, available_files: set) -> Optional[str]:
        """Find the best matching file for an orphaned table entry"""
        if not available_files:
            return None

        # Try to match by scanning each available file and comparing metadata
        best_match = None
        best_score = 0

        for file_path in available_files:
            try:
                file_data = self.scanner.scan_file(file_path)
                if not file_data:
                    continue

                # Calculate match score based on metadata similarity
                score = 0

                # Name match (highest weight)
                if file_data.get('name') and orphaned_table.name:
                    if file_data['name'].lower() == orphaned_table.name.lower():
                        score += 10
                    elif orphaned_table.name.lower() in file_data['name'].lower():
                        score += 7
                    elif file_data['name'].lower() in orphaned_table.name.lower():
                        score += 5

                # Manufacturer match
                if (file_data.get('manufacturer') and orphaned_table.manufacturer and
                    file_data['manufacturer'].lower() == orphaned_table.manufacturer.lower()):
                    score += 3

                # Year match
                if (file_data.get('year') and orphaned_table.year and
                    file_data['year'] == orphaned_table.year):
                    score += 2

                # Author match
                if (file_data.get('author') and orphaned_table.author and
                    file_data['author'].lower() == orphaned_table.author.lower()):
                    score += 2

                # ROM name match
                if (file_data.get('rom_name') and orphaned_table.rom_name and
                    file_data['rom_name'].lower() == orphaned_table.rom_name.lower()):
                    score += 2

                # File size similarity (rough match)
                if file_data.get('file_size') and orphaned_table.file_size:
                    size_diff = abs(file_data['file_size'] - orphaned_table.file_size)
                    if size_diff == 0:
                        score += 2
                    elif size_diff < 1024 * 1024:  # Within 1MB
                        score += 1

                if score > best_score:
                    best_score = score
                    best_match = file_path

            except Exception as e:
                self.logger.error(f"Error analyzing file {file_path}: {e}")

        # Only return a match if we have a reasonable confidence score
        if best_score >= 5:  # Minimum threshold for a match
            return best_match

        return None

    def rescan_all_media(self) -> Dict[str, int]:
        """Rescan media files for all tables and update database"""
        result = {
            'total': 0,
            'updated': 0,
            'no_changes': 0,
            'errors': 0
        }

        if not self.media_manager:
            self.logger.warning("MediaManager not available, cannot scan media")
            return result

        try:
            tables = self.get_all_tables(enabled_only=False)
            result['total'] = len(tables)

            with self.db.get_session() as session:
                for table in tables:
                    try:
                        # Get the table from this session
                        db_table = session.query(Table).filter(Table.id == table.id).first()
                        if db_table:
                            updated = self._update_table_media(db_table)
                            if updated:
                                result['updated'] += 1
                                self.logger.debug(f"Updated media for: {table.name}")
                            else:
                                result['no_changes'] += 1
                    except Exception as e:
                        result['errors'] += 1
                        self.logger.error(f"Error scanning media for table {table.name}: {e}")

                session.commit()

            self.logger.info(f"Media scan complete: {result['updated']} updated, {result['no_changes']} unchanged, {result['errors']} errors")

        except Exception as e:
            self.logger.error(f"Failed to rescan all media: {e}")
            result['errors'] += 1

        return result

    def update_media_for_table(self, table_id: int) -> bool:
        """Update media paths for a single table"""
        if not self.media_manager:
            self.logger.warning("MediaManager not available")
            return False

        try:
            with self.db.get_session() as session:
                table = session.query(Table).filter(Table.id == table_id).first()
                if not table:
                    self.logger.warning(f"Table ID {table_id} not found")
                    return False

                updated = self._update_table_media(table)
                if updated:
                    session.commit()
                    self.logger.info(f"Updated media for table: {table.name}")
                    return True
                else:
                    self.logger.debug(f"No media changes for table: {table.name}")
                    return False

        except Exception as e:
            self.logger.error(f"Failed to update media for table {table_id}: {e}")
            return False

    def remove_missing_tables(self, mark_disabled: bool = True) -> Dict[str, int]:
        """Remove or disable tables whose files no longer exist"""
        result = {
            'checked': 0,
            'missing': 0,
            'disabled': 0,
            'removed': 0
        }

        try:
            tables = self.get_all_tables(enabled_only=False)
            result['checked'] = len(tables)

            with self.db.get_session() as session:
                for table in tables:
                    if not Path(table.file_path).exists():
                        result['missing'] += 1

                        # Get the table from this session
                        db_table = session.query(Table).filter(Table.id == table.id).first()
                        if db_table:
                            if mark_disabled:
                                db_table.enabled = False
                                db_table.updated_at = datetime.utcnow()
                                result['disabled'] += 1
                                self.logger.info(f"Disabled missing table: {table.name}")
                            else:
                                session.delete(db_table)
                                result['removed'] += 1
                                self.logger.info(f"Removed missing table: {table.name}")

                session.commit()

        except Exception as e:
            self.logger.error(f"Failed to remove missing tables: {e}")

        return result