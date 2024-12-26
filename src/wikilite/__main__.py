"""
Main entry point for the wikilite package.
"""

import click
import subprocess
from pathlib import Path
from . import __version__
from .populate_db import populate_database

DEFAULT_DB = "wikidict.db"


@click.group()
@click.version_option(version=__version__)
def cli():
    """wikilite - Wiktionary data processing tool"""
    pass


@cli.command()
@click.option(
    "--input",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Input JSONL file path",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output SQLite database file path",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force overwrite if output file exists",
)
def populate(input: Path, output: Path, force: bool):
    """Populate database from JSONL file."""
    try:
        populate_database(input_path=input, output_path=output, force=force)
    except FileExistsError as e:
        click.echo(str(e), err=True)
        exit(1)


@cli.command()
def ui():
    """Launch the Streamlit UI for browsing the dictionary."""
    app_path = Path(__file__).parent / "app.py"
    subprocess.run(["streamlit", "run", str(app_path)])


def main():
    """Main entry point for the wikilite CLI."""
    cli()


if __name__ == "__main__":
    main()
