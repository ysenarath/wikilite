"""
Main entry point for the wikilite package.
"""

from . import __version__

DEFAULT_DB = "wikidict.db"


def main():
    """Main entry point for the wikilite CLI."""
    print(f"wikilite v{__version__}")


if __name__ == "__main__":
    main()
