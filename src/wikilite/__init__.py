"""
wikilite - A lightweight SQLite-based storage for Wikidict senses
"""

from pathlib import Path

__version__ = "0.1.0"


class WikiLite:
    """SQLite-based storage for Wikidict senses."""

    def __init__(self, path: str):
        """Initialize WikiLite with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.path = Path(path)
