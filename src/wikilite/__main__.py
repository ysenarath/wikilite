"""Command-line interface for wikilite."""

import click
from pathlib import Path

from .database import Database, generate_fingerprint, get_cache_dir
from .utils import wiktextract
from .importer import WiktionaryImporter


@click.group()
def cli():
    """Wikilite - A lightweight SQLite-based storage for Wikidict senses."""
    pass


@cli.command()
def init():
    """Initialize the default database."""
    db = Database()
    db.create_all()
    click.echo(f"Default database initialized at: {get_cache_dir() / 'default.db'}")


@cli.command()
@click.argument(
    "jsonl-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--batch-size",
    type=int,
    default=100_000,
    help="Number of entries to process before committing (default: 100000)",
)
def import_data(jsonl_file: Path, batch_size: int):
    """Import data from a JSONL file into the database."""
    # Generate fingerprint from input file
    fingerprint = generate_fingerprint(jsonl_file)
    db = Database(fingerprint)

    # Ensure database is initialized
    db.create_all()

    click.echo(f"Using database: {get_cache_dir() / f'{fingerprint}.db'}")

    with db.session() as session:
        importer = WiktionaryImporter(session, batch_size=batch_size)

        # Import entries
        click.echo(f"Importing entries (batch size: {batch_size})...")
        entries_processed = 0
        for word in wiktextract.load(jsonl_file):
            importer.import_word(word)
            entries_processed += 1
            if entries_processed % batch_size == 0:
                click.echo(f"Processed {entries_processed} entries...")

        # Ensure any remaining entries are saved
        importer.finalize()
        click.echo(f"Processed {entries_processed} entries total.")

    click.echo("Import completed successfully!")


@cli.command()
@click.argument(
    "jsonl-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def reset(jsonl_file: Path):
    """Reset the database for a specific JSONL file."""
    if not click.confirm("This will delete all data. Are you sure?"):
        return

    fingerprint = generate_fingerprint(jsonl_file)
    db = Database(fingerprint)
    db.drop_all()
    db.create_all()
    click.echo(f"Database reset completed for {jsonl_file.name}")


def main():
    """Entry point for the wikilite CLI."""
    cli()


if __name__ == "__main__":
    main()
