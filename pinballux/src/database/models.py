"""
Database models for PinballUX table management
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.engine import Engine

from ..core.logger import get_logger

Base = declarative_base()
logger = get_logger(__name__)


class Table(Base):
    """Main table model for VPX files"""
    __tablename__ = 'tables'

    id = Column(Integer, primary_key=True)

    # Basic table information
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    manufacturer = Column(String(100), index=True)
    year = Column(Integer, index=True)
    type = Column(String(50))  # SS (Solid State), EM (Electromechanical), etc.

    # File information
    file_path = Column(String(500), nullable=False, unique=True)
    file_size = Column(Integer)
    file_modified = Column(DateTime)

    # VPX metadata
    vpx_version = Column(String(20))
    table_version = Column(String(50))
    author = Column(String(255))
    release_date = Column(DateTime)

    # Game information
    players = Column(Integer, default=1)
    rom_name = Column(String(100))

    # Media paths
    playfield_image = Column(String(500))
    backglass_image = Column(String(500))
    backglass_video = Column(String(500))
    dmd_image = Column(String(500))
    dmd_video = Column(String(500))
    topper_image = Column(String(500))
    topper_video = Column(String(500))
    wheel_image = Column(String(500))
    table_video = Column(String(500))
    table_audio = Column(String(500))
    launch_audio = Column(String(500))

    # User data
    rating = Column(Float, default=0.0)
    play_count = Column(Integer, default=0)
    last_played = Column(DateTime)
    total_play_time = Column(Integer, default=0)  # seconds
    favorite = Column(Boolean, default=False)

    # Status
    enabled = Column(Boolean, default=True)
    working = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    categories = relationship("TableCategory", back_populates="table")
    play_sessions = relationship("PlaySession", back_populates="table", order_by="PlaySession.start_time.desc()")

    def __repr__(self):
        return f"<Table(name='{self.name}', manufacturer='{self.manufacturer}', year={self.year})>"

    @property
    def display_name(self) -> str:
        """Get formatted display name"""
        if self.manufacturer and self.year:
            return f"{self.name} ({self.manufacturer} {self.year})"
        elif self.manufacturer:
            return f"{self.name} ({self.manufacturer})"
        elif self.year:
            return f"{self.name} ({self.year})"
        return self.name

    @property
    def average_session_time(self) -> float:
        """Get average play session time in minutes"""
        if not self.play_sessions or self.play_count == 0:
            return 0.0
        return (self.total_play_time / 60.0) / self.play_count


class Category(Base):
    """Categories for organizing tables"""
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    color = Column(String(7))  # hex color code
    icon = Column(String(50))  # icon name or path

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tables = relationship("TableCategory", back_populates="category")

    def __repr__(self):
        return f"<Category(name='{self.name}')>"


class TableCategory(Base):
    """Many-to-many relationship between tables and categories"""
    __tablename__ = 'table_categories'

    id = Column(Integer, primary_key=True)
    table_id = Column(Integer, ForeignKey('tables.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    table = relationship("Table", back_populates="categories")
    category = relationship("Category", back_populates="tables")


class PlaySession(Base):
    """Individual play sessions for statistics"""
    __tablename__ = 'play_sessions'

    id = Column(Integer, primary_key=True)
    table_id = Column(Integer, ForeignKey('tables.id'), nullable=False)

    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime)
    duration = Column(Integer)  # seconds

    # Session data
    score = Column(Integer)
    player_count = Column(Integer, default=1)
    completed = Column(Boolean, default=False)  # Did they finish the game?

    # Relationships
    table = relationship("Table", back_populates="play_sessions")

    def __repr__(self):
        return f"<PlaySession(table='{self.table.name if self.table else 'Unknown'}', start_time='{self.start_time}')>"

    @property
    def duration_minutes(self) -> float:
        """Get session duration in minutes"""
        if self.duration:
            return self.duration / 60.0
        return 0.0


class Settings(Base):
    """Application settings stored in database"""
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text)
    type = Column(String(20), default='string')  # string, integer, float, boolean, json

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Setting(key='{self.key}', value='{self.value}')>"


class FTPMediaCache(Base):
    """Cache of FTP media directory listings"""
    __tablename__ = 'ftp_media_cache'

    id = Column(Integer, primary_key=True)
    directory = Column(String(500), nullable=False, index=True)  # FTP directory path
    filename = Column(String(500), nullable=False, index=True)  # File name
    file_size = Column(Integer)  # File size in bytes
    media_type = Column(String(50), index=True)  # table_audio, backglass_image, etc.

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FTPMediaCache(directory='{self.directory}', filename='{self.filename}')>"


class DatabaseManager:
    """Database management class"""

    def __init__(self, database_url: str = None):
        if database_url is None:
            # Default to SQLite in user's config directory
            from pathlib import Path
            db_dir = Path.home() / ".config" / "pinballux"
            db_dir.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{db_dir / 'pinballux.db'}"

        self.database_url = database_url
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None

        logger.info(f"Initializing database: {database_url}")

    def initialize(self):
        """Initialize database connection and create tables"""
        try:
            self.engine = create_engine(self.database_url, echo=False)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            # Create all tables
            Base.metadata.create_all(bind=self.engine)

            # Run migrations for schema updates
            self._run_migrations()

            # Create default categories
            self._create_default_categories()

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _run_migrations(self):
        """Run database migrations for schema updates"""
        try:
            from sqlalchemy import text, inspect

            inspector = inspect(self.engine)

            if 'tables' in inspector.get_table_names():
                existing_columns = {col['name'] for col in inspector.get_columns('tables')}

                # List of new columns to add
                new_columns = {
                    'backglass_video': 'VARCHAR(500)',
                    'dmd_video': 'VARCHAR(500)',
                    'topper_video': 'VARCHAR(500)',
                    'wheel_image': 'VARCHAR(500)',
                    'table_audio': 'VARCHAR(500)',
                    'launch_audio': 'VARCHAR(500)'
                }

                # Add missing columns
                with self.engine.begin() as conn:
                    for col_name, col_type in new_columns.items():
                        if col_name not in existing_columns:
                            logger.info(f"Adding column: {col_name}")
                            conn.execute(text(f"ALTER TABLE tables ADD COLUMN {col_name} {col_type}"))

                logger.info("Database migrations completed")

        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            # Don't raise - continue with initialization

    def get_session(self) -> Session:
        """Get a database session"""
        if self.SessionLocal is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.SessionLocal()

    def _create_default_categories(self):
        """Create default table categories"""
        default_categories = [
            {"name": "Favorites", "description": "Favorite tables", "color": "#ff6b6b", "icon": "star"},
            {"name": "Modern Stern", "description": "Modern Stern tables", "color": "#4ecdc4", "icon": "modern"},
            {"name": "Gottlieb", "description": "Gottlieb tables", "color": "#45b7d1", "icon": "gottlieb"},
            {"name": "Williams/Bally", "description": "Williams and Bally tables", "color": "#f9ca24", "icon": "williams"},
            {"name": "Classic", "description": "Classic tables", "color": "#f0932b", "icon": "classic"},
            {"name": "Original", "description": "Original/Fantasy tables", "color": "#eb4d4b", "icon": "original"},
            {"name": "Recently Played", "description": "Recently played tables", "color": "#6c5ce7", "icon": "recent"},
        ]

        try:
            with self.get_session() as session:
                for cat_data in default_categories:
                    # Check if category already exists
                    existing = session.query(Category).filter(Category.name == cat_data["name"]).first()
                    if not existing:
                        category = Category(**cat_data)
                        session.add(category)

                session.commit()
                logger.info("Default categories created")

        except Exception as e:
            logger.error(f"Failed to create default categories: {e}")

    def get_table_by_path(self, file_path: str) -> Optional[Table]:
        """Get table by file path"""
        try:
            with self.get_session() as session:
                return session.query(Table).filter(Table.file_path == file_path).first()
        except Exception as e:
            logger.error(f"Failed to get table by path {file_path}: {e}")
            return None

    def get_all_tables(self, enabled_only: bool = True) -> List[Table]:
        """Get all tables"""
        try:
            with self.get_session() as session:
                query = session.query(Table)
                if enabled_only:
                    query = query.filter(Table.enabled == True)
                return query.order_by(Table.name).all()
        except Exception as e:
            logger.error(f"Failed to get all tables: {e}")
            return []

    def search_tables(self, search_term: str, manufacturer: str = None) -> List[Table]:
        """Search tables by name, manufacturer, etc."""
        try:
            with self.get_session() as session:
                query = session.query(Table).filter(Table.enabled == True)

                if search_term:
                    search_term = f"%{search_term}%"
                    query = query.filter(
                        Table.name.ilike(search_term) |
                        Table.description.ilike(search_term) |
                        Table.manufacturer.ilike(search_term) |
                        Table.author.ilike(search_term)
                    )

                if manufacturer:
                    query = query.filter(Table.manufacturer == manufacturer)

                return query.order_by(Table.name).all()
        except Exception as e:
            logger.error(f"Failed to search tables: {e}")
            return []

    def record_play_session(self, table_id: int, duration: int, score: int = None) -> PlaySession:
        """Record a completed play session"""
        try:
            with self.get_session() as session:
                # Create play session
                play_session = PlaySession(
                    table_id=table_id,
                    end_time=datetime.utcnow(),
                    duration=duration,
                    score=score,
                    completed=True
                )
                play_session.start_time = play_session.end_time - datetime.timedelta(seconds=duration)

                session.add(play_session)

                # Update table statistics
                table = session.query(Table).filter(Table.id == table_id).first()
                if table:
                    table.play_count += 1
                    table.total_play_time += duration
                    table.last_played = datetime.utcnow()
                    table.updated_at = datetime.utcnow()

                session.commit()
                logger.info(f"Recorded play session for table ID {table_id}")
                return play_session

        except Exception as e:
            logger.error(f"Failed to record play session: {e}")
            raise