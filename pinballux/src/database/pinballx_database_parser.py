"""
PinballX Database CSV Parser

Parses the PinballX database CSV file to extract table metadata
including theme, IPDB number, authors, and other interesting facts.
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional
from ..core.logger import get_logger

logger = get_logger(__name__)


class PinballXDatabaseParser:
    """Parser for PinballX database CSV files"""

    def __init__(self, csv_path: str):
        """Initialize parser with CSV file path"""
        self.csv_path = Path(csv_path)
        self.data: List[Dict] = []

    def parse(self) -> List[Dict]:
        """Parse the CSV file and return list of table data"""
        if not self.csv_path.exists():
            logger.error(f"CSV file not found: {self.csv_path}")
            return []

        try:
            with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # Extract data from CSV
                    table_data = self._parse_row(row)
                    if table_data:
                        self.data.append(table_data)

            logger.info(f"Parsed {len(self.data)} tables from {self.csv_path.name}")
            return self.data

        except Exception as e:
            logger.error(f"Failed to parse CSV file {self.csv_path}: {e}")
            return []

    def _parse_row(self, row: Dict) -> Optional[Dict]:
        """Parse a single CSV row into table data"""
        try:
            # Extract table name, manufacturer, and year from the combined field
            full_name = row.get('Table Name (Manufacturer Year)', '').strip()
            if not full_name:
                return None

            # Parse the full name to extract base name, manufacturer, year
            name, manufacturer, year = self._parse_table_name(full_name)

            # Override with separate fields if available
            if row.get('Manufacturer'):
                manufacturer = row['Manufacturer'].strip()
            if row.get('Year'):
                try:
                    year = int(row['Year'])
                except (ValueError, TypeError):
                    pass

            # Parse IPDB number
            ipdb_number = None
            if row.get('IPDB Number'):
                try:
                    ipdb_str = row['IPDB Number'].strip()
                    if ipdb_str and ipdb_str != '-':
                        ipdb_number = int(ipdb_str)
                except (ValueError, TypeError):
                    pass

            # Parse player count
            players = 1
            if row.get('Player(s)'):
                try:
                    players = int(row['Player(s)'].strip())
                except (ValueError, TypeError):
                    pass

            return {
                'name': name,
                'full_name': full_name,
                'manufacturer': manufacturer,
                'year': year,
                'theme': row.get('Theme', '').strip() or None,
                'players': players,
                'ipdb_number': ipdb_number,
                'description': row.get('Description(s)', '').strip() or None,
                'type': row.get('Type', '').strip() or None,  # EM, SS, PM
                'vp_version': row.get('VP Version', '').strip() or None,  # VPX, FP
                'author': row.get('Table Author(s)', '').strip() or None,
                'table_version': row.get('Table Version', '').strip() or None,
                'table_date': row.get('Table Date', '').strip() or None,
            }

        except Exception as e:
            logger.warning(f"Failed to parse row: {e}")
            return None

    def _parse_table_name(self, full_name: str) -> tuple:
        """
        Parse table name in format: "Table Name (Manufacturer Year) Author Version"

        Returns: (name, manufacturer, year)
        """
        name = full_name
        manufacturer = None
        year = None

        # Look for pattern: "Name (Manufacturer Year) ..."
        if '(' in full_name and ')' in full_name:
            parts = full_name.split('(', 1)
            name = parts[0].strip()

            # Extract manufacturer and year from parentheses
            paren_content = parts[1].split(')', 1)[0].strip()
            paren_parts = paren_content.rsplit(' ', 1)

            if len(paren_parts) == 2:
                manufacturer = paren_parts[0].strip()
                try:
                    year = int(paren_parts[1])
                except (ValueError, TypeError):
                    # Year not found, entire content is manufacturer
                    manufacturer = paren_content
            else:
                manufacturer = paren_content

        return name, manufacturer, year

    def find_table_by_name(self, table_name: str, manufacturer: str = None, year: int = None) -> Optional[Dict]:
        """
        Find a table in the parsed data by name, manufacturer, and year

        Uses fuzzy matching to handle variations in table names
        """
        if not self.data:
            return None

        # Normalize search term
        search_name = self._normalize_name(table_name)

        best_match = None
        best_score = 0

        for table in self.data:
            # Calculate match score
            score = 0

            # Check name match
            table_name_norm = self._normalize_name(table['name'])
            if search_name == table_name_norm:
                score += 100
            elif search_name in table_name_norm or table_name_norm in search_name:
                score += 50

            # Check manufacturer match
            if manufacturer and table.get('manufacturer'):
                mfr_search = self._normalize_name(manufacturer)
                mfr_table = self._normalize_name(table['manufacturer'])
                if mfr_search == mfr_table:
                    score += 30
                elif mfr_search in mfr_table or mfr_table in mfr_search:
                    score += 15

            # Check year match
            if year and table.get('year'):
                if year == table['year']:
                    score += 20

            # Update best match
            if score > best_score:
                best_score = score
                best_match = table

        # Only return match if score is reasonable (at least 50)
        if best_score >= 50:
            logger.debug(f"Found match for '{table_name}' (score: {best_score}): {best_match['full_name']}")
            return best_match

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison (lowercase, no special chars)"""
        if not name:
            return ''

        # Convert to lowercase
        name = name.lower()

        # Remove common special characters
        for char in [':', '.', ',', '-', '_', '!', '?', "'", '"']:
            name = name.replace(char, ' ')

        # Collapse multiple spaces
        name = ' '.join(name.split())

        return name

    def get_statistics(self) -> Dict:
        """Get statistics about the parsed data"""
        if not self.data:
            return {}

        manufacturers = set()
        themes = set()
        years = []
        types = set()

        for table in self.data:
            if table.get('manufacturer'):
                manufacturers.add(table['manufacturer'])
            if table.get('theme'):
                # Split themes by comma
                for theme in table['theme'].split(','):
                    themes.add(theme.strip())
            if table.get('year'):
                years.append(table['year'])
            if table.get('type'):
                types.add(table['type'])

        return {
            'total_tables': len(self.data),
            'manufacturers': len(manufacturers),
            'themes': len(themes),
            'types': list(types),
            'year_range': (min(years), max(years)) if years else None,
        }
