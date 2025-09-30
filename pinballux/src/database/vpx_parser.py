"""
VPX file parser for extracting table metadata
"""

import os
import re
import struct
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any
import olefile

from ..core.logger import get_logger

logger = get_logger(__name__)


class VPXParser:
    """Parser for Visual Pinball X (.vpx) files"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def parse_vpx_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a VPX file and extract metadata"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"VPX file not found: {file_path}")

            metadata = {
                'file_path': file_path,
                'file_size': os.path.getsize(file_path),
                'file_modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
                'name': Path(file_path).stem,
                'manufacturer': '',
                'year': None,
                'author': '',
                'description': '',
                'table_version': '',
                'vpx_version': '',
                'rom_name': '',
                'players': 1,
                'type': 'SS',  # Default to Solid State
                'working': True,
                'enabled': True
            }

            # Try to parse VPX file using olefile
            if olefile.isOleFile(file_path):
                self._parse_ole_structure(file_path, metadata)
            else:
                self.logger.warning(f"File {file_path} is not a valid OLE file")
                # Fallback to filename parsing
                self._parse_filename(file_path, metadata)

            # Extract additional info from filename if not found in file
            self._enhance_metadata_from_filename(metadata)

            return metadata

        except Exception as e:
            self.logger.error(f"Failed to parse VPX file {file_path}: {e}")
            # Return basic metadata on failure
            return {
                'file_path': file_path,
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                'file_modified': datetime.fromtimestamp(os.path.getmtime(file_path)) if os.path.exists(file_path) else datetime.now(),
                'name': Path(file_path).stem,
                'manufacturer': '',
                'year': None,
                'author': '',
                'description': f"Failed to parse: {str(e)}",
                'table_version': '',
                'vpx_version': '',
                'rom_name': '',
                'players': 1,
                'type': 'SS',
                'working': False,
                'enabled': True
            }

    def _parse_ole_structure(self, file_path: str, metadata: Dict[str, Any]):
        """Parse OLE compound document structure"""
        try:
            with olefile.OleFileIO(file_path) as ole:
                # List all streams for debugging
                self.logger.debug(f"OLE streams in {file_path}: {ole.listdir()}")

                # Try to read common VP streams
                self._read_game_data_stream(ole, metadata)
                self._read_table_info_stream(ole, metadata)
                self._read_script_stream(ole, metadata)

        except Exception as e:
            self.logger.error(f"Failed to parse OLE structure: {e}")

    def _read_game_data_stream(self, ole: olefile.OleFileIO, metadata: Dict[str, Any]):
        """Read GameData stream from VPX file"""
        try:
            # GameData stream contains table properties
            if ole._olestream_exists(['GameData']):
                with ole.open('GameData') as stream:
                    data = stream.read()
                    # Parse binary data for table properties
                    self._parse_game_data_binary(data, metadata)

        except Exception as e:
            self.logger.debug(f"Could not read GameData stream: {e}")

    def _read_table_info_stream(self, ole: olefile.OleFileIO, metadata: Dict[str, Any]):
        """Read TableInfo stream from VPX file"""
        try:
            # Look for various info streams
            streams_to_check = ['TableInfo', 'GameData', 'Version']

            for stream_path in ole.listdir():
                stream_name = stream_path[-1] if isinstance(stream_path, list) else stream_path

                if stream_name in ['Version', 'GameData']:
                    try:
                        with ole.open(stream_path) as stream:
                            data = stream.read()
                            # Try to extract text information
                            self._extract_text_from_binary(data, metadata)
                    except Exception as e:
                        self.logger.debug(f"Could not read stream {stream_name}: {e}")

        except Exception as e:
            self.logger.debug(f"Could not read table info: {e}")

    def _read_script_stream(self, ole: olefile.OleFileIO, metadata: Dict[str, Any]):
        """Read script stream to extract table information from VBScript"""
        try:
            # Look for script-related streams
            for stream_path in ole.listdir():
                stream_name = stream_path[-1] if isinstance(stream_path, list) else stream_path

                if 'script' in stream_name.lower() or 'vbs' in stream_name.lower():
                    try:
                        with ole.open(stream_path) as stream:
                            script_data = stream.read()
                            try:
                                # Try to decode as text
                                script_text = script_data.decode('utf-8', errors='ignore')
                                self._parse_script_content(script_text, metadata)
                            except:
                                # Try other encodings
                                try:
                                    script_text = script_data.decode('latin-1', errors='ignore')
                                    self._parse_script_content(script_text, metadata)
                                except:
                                    pass
                    except Exception as e:
                        self.logger.debug(f"Could not read script stream {stream_name}: {e}")

        except Exception as e:
            self.logger.debug(f"Could not read script content: {e}")

    def _parse_game_data_binary(self, data: bytes, metadata: Dict[str, Any]):
        """Parse binary GameData for table properties"""
        try:
            # VPX files store properties in binary format
            # This is a simplified parser for common properties

            # Look for text strings in the binary data
            text_data = data.decode('utf-8', errors='ignore')

            # Extract common properties using regex
            patterns = {
                'author': r'(?i)author["\s]*[=:]["\s]*([^";\n\r]+)',
                'description': r'(?i)description["\s]*[=:]["\s]*([^";\n\r]+)',
                'manufacturer': r'(?i)manufacturer["\s]*[=:]["\s]*([^";\n\r]+)',
                'table_version': r'(?i)(?:table_?)?version["\s]*[=:]["\s]*([^";\n\r]+)',
                'rom_name': r'(?i)rom["\s]*[=:]["\s]*([^";\n\r]+)',
            }

            for key, pattern in patterns.items():
                match = re.search(pattern, text_data)
                if match:
                    value = match.group(1).strip()
                    if value and value != '""' and value != "''":
                        metadata[key] = value

        except Exception as e:
            self.logger.debug(f"Could not parse game data binary: {e}")

    def _extract_text_from_binary(self, data: bytes, metadata: Dict[str, Any]):
        """Extract text information from binary data"""
        try:
            # Try different encodings to extract readable text
            for encoding in ['utf-8', 'utf-16', 'latin-1']:
                try:
                    text = data.decode(encoding, errors='ignore')
                    # Clean up the text and look for useful information
                    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)

                    # Look for version information
                    version_match = re.search(r'(\d+\.\d+[\.\d]*)', text)
                    if version_match and not metadata.get('vpx_version'):
                        metadata['vpx_version'] = version_match.group(1)

                    break
                except:
                    continue

        except Exception as e:
            self.logger.debug(f"Could not extract text from binary: {e}")

    def _parse_script_content(self, script_text: str, metadata: Dict[str, Any]):
        """Parse VBScript content for table information"""
        try:
            # Common VBScript patterns in VP tables
            patterns = {
                'rom_name': r'(?i)(?:cGameName\s*=\s*["\']([^"\']+)|GameName\s*=\s*["\']([^"\']+)|ROM\s*=\s*["\']([^"\']+))',
                'author': r'(?i)author\s*=\s*["\']([^"\']+)',
                'table_version': r'(?i)(?:table_?)?version\s*=\s*["\']([^"\']+)',
                'description': r'(?i)description\s*=\s*["\']([^"\']+)',
            }

            for key, pattern in patterns.items():
                match = re.search(pattern, script_text)
                if match:
                    # Get the first non-empty group
                    value = next((g for g in match.groups() if g), None)
                    if value and value.strip():
                        metadata[key] = value.strip()

        except Exception as e:
            self.logger.debug(f"Could not parse script content: {e}")

    def _parse_filename(self, file_path: str, metadata: Dict[str, Any]):
        """Extract information from filename when OLE parsing fails"""
        filename = Path(file_path).stem

        # Common filename patterns
        # Pattern: "TableName (Manufacturer Year)"
        pattern1 = r'^(.+?)\s*\(([^)]+)\s+(\d{4})\).*$'
        match = re.match(pattern1, filename)
        if match:
            metadata['name'] = match.group(1).strip()
            metadata['manufacturer'] = match.group(2).strip()
            metadata['year'] = int(match.group(3))
            return

        # Pattern: "TableName (Manufacturer)"
        pattern2 = r'^(.+?)\s*\(([^)]+)\).*$'
        match = re.match(pattern2, filename)
        if match:
            metadata['name'] = match.group(1).strip()
            metadata['manufacturer'] = match.group(2).strip()
            return

        # Pattern: "Manufacturer - TableName (Year)"
        pattern3 = r'^([^-]+)\s*-\s*(.+?)\s*\((\d{4})\).*$'
        match = re.match(pattern3, filename)
        if match:
            metadata['manufacturer'] = match.group(1).strip()
            metadata['name'] = match.group(2).strip()
            metadata['year'] = int(match.group(3))
            return

        # Just use the filename as the table name
        metadata['name'] = filename

    def _enhance_metadata_from_filename(self, metadata: Dict[str, Any]):
        """Enhance metadata using filename patterns"""
        filename = Path(metadata['file_path']).stem

        # Look for year in filename if not already found
        if not metadata.get('year'):
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filename)
            if year_match:
                metadata['year'] = int(year_match.group(1))

        # Look for manufacturer names in filename
        if not metadata.get('manufacturer'):
            manufacturers = [
                'Williams', 'Bally', 'Stern', 'Gottlieb', 'Data East',
                'Sega', 'Midway', 'Capcom', 'Taito', 'Zaccaria',
                'Alvin G', 'Premier', 'Hankin', 'Chicago Coin',
                'Game Plan', 'Playmatic', 'Recel', 'Spinball'
            ]

            filename_lower = filename.lower()
            for manufacturer in manufacturers:
                if manufacturer.lower() in filename_lower:
                    metadata['manufacturer'] = manufacturer
                    break

        # Determine table type based on year
        if metadata.get('year'):
            year = metadata['year']
            if year < 1977:
                metadata['type'] = 'EM'  # Electromechanical
            else:
                metadata['type'] = 'SS'  # Solid State

        # Set description if empty
        if not metadata.get('description'):
            desc_parts = []
            if metadata.get('manufacturer'):
                desc_parts.append(metadata['manufacturer'])
            if metadata.get('year'):
                desc_parts.append(str(metadata['year']))
            if metadata.get('type'):
                desc_parts.append(metadata['type'])

            if desc_parts:
                metadata['description'] = f"Pinball table by {' '.join(desc_parts)}"


class TableScanner:
    """Scanner for finding and cataloging VPX files"""

    def __init__(self):
        self.parser = VPXParser()
        self.logger = get_logger(__name__)

    def scan_directory(self, directory: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """Scan directory for VPX files and extract metadata"""
        tables = []

        try:
            directory_path = Path(directory)
            if not directory_path.exists():
                self.logger.error(f"Directory does not exist: {directory}")
                return tables

            # Find all VPX files
            if recursive:
                vpx_files = list(directory_path.rglob("*.vpx"))
            else:
                vpx_files = list(directory_path.glob("*.vpx"))

            self.logger.info(f"Found {len(vpx_files)} VPX files in {directory}")

            for vpx_file in vpx_files:
                try:
                    self.logger.debug(f"Parsing VPX file: {vpx_file}")
                    metadata = self.parser.parse_vpx_file(str(vpx_file))
                    tables.append(metadata)
                except Exception as e:
                    self.logger.error(f"Failed to parse {vpx_file}: {e}")
                    # Add a basic entry even if parsing fails
                    tables.append({
                        'file_path': str(vpx_file),
                        'name': vpx_file.stem,
                        'file_size': vpx_file.stat().st_size,
                        'file_modified': datetime.fromtimestamp(vpx_file.stat().st_mtime),
                        'working': False,
                        'enabled': True,
                        'description': f"Parse failed: {str(e)}"
                    })

        except Exception as e:
            self.logger.error(f"Failed to scan directory {directory}: {e}")

        return tables

    def scan_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Scan a single VPX file"""
        try:
            return self.parser.parse_vpx_file(file_path)
        except Exception as e:
            self.logger.error(f"Failed to scan file {file_path}: {e}")
            return None