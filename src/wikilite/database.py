"""Database management module for wikilite."""
import hashlib
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def generate_fingerprint(file_path: Path | str) -> str:
    """Generate a fingerprint for the input file."""
    file_path = Path(file_path)
    # Use file size and modification time for fingerprint
    stats = file_path.stat()
    fingerprint = f"{file_path.name}_{stats.st_size}_{int(stats.st_mtime)}"
    return hashlib.md5(fingerprint.encode()).hexdigest()[:12]


def get_cache_dir() -> Path:
    """Get the cache directory path."""
    return Path.home() / ".cache" / "wikilite"


def get_db_path(fingerprint: Optional[str] = None) -> Path:
    """Get database path for given fingerprint."""
    cache_dir = get_cache_dir()
    if fingerprint:
        return cache_dir / f"{fingerprint}.db"
    return cache_dir / "default.db"


class Database:
    """Database connection manager."""
    
    def __init__(self, fingerprint: Optional[str] = None):
        """Initialize database with optional fingerprint."""
        db_path = get_db_path(fingerprint)
        
        # Ensure cache directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create database engine with absolute path
        self.engine = create_engine(f"sqlite:///{db_path.absolute()}", echo=False)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Get a database session context manager."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_all(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(self.engine)
    
    def drop_all(self) -> None:
        """Drop all database tables."""
        Base.metadata.drop_all(self.engine)
