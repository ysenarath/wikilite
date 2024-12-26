"""Script to populate SQLite database from Wiktionary JSONL data."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tqdm import tqdm

from wikilite.models import (
    Base,
    Entry,
    Sense,
    Form,
    Example,
    Translation,
    Pronunciation,
)

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Set up logging
logging.basicConfig(
    handlers=[logging.FileHandler(logs_dir / "import.log")],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def validate_entry(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate and clean entry data.

    Returns:
        Dict with cleaned data if valid, None if invalid
    """
    # Required fields
    if not all(key in data for key in ["word", "lang"]):
        logging.error(
            f"Missing required fields in entry: {data.get('word', 'UNKNOWN')}"
        )
        return None

    # Clean and validate data
    cleaned = {
        "title": str(data["word"])[:255],  # Truncate if too long
        "language": str(data["lang"])[:50],
        "part_of_speech": str(data.get("pos", ""))[:50] if data.get("pos") else None,
        "etymology": data.get("etymology"),
    }

    # Validate senses
    senses = []
    for sense_data in data.get("senses", []):
        if not sense_data.get("glosses"):
            logging.warning(f"Skipping sense without gloss for word: {data['word']}")
            continue

        sense = {
            "definition": " | ".join(sense_data["glosses"]),
            "notes": sense_data.get("notes"),
            "examples": [],
            "translations": [],
        }

        # Process examples
        for example in sense_data.get("examples", []):
            if isinstance(example, str):
                sense["examples"].append({"text": example, "translation": None})
            elif isinstance(example, dict):
                sense["examples"].append(
                    {
                        "text": example.get("text", ""),
                        "translation": example.get("translation"),
                    }
                )

        # Process translations
        for trans in sense_data.get("translations", []):
            if isinstance(trans, dict):
                sense["translations"].append(
                    {
                        "language": trans.get("lang", "")[:50],
                        "text": trans.get("word", "")[:255],
                        "notes": trans.get("sense"),  # Using 'sense' field as notes
                    }
                )

        senses.append(sense)

    if not senses:
        logging.warning(f"No valid senses found for word: {data['word']}")
        return None

    cleaned["senses"] = senses

    # Process forms
    forms = []
    for form_data in data.get("forms", []):
        if not form_data.get("form"):
            continue
        forms.append(
            {
                "form": str(form_data["form"])[:255],
                "tags": " | ".join(form_data.get("tags", []))[:255],
            }
        )
    cleaned["forms"] = forms

    # Process pronunciations
    pronunciations = []
    for pron in data.get("pronunciations", []):
        if not pron.get("ipa"):
            continue
        pronunciations.append(
            {
                "text": str(pron["ipa"])[:255],
                "audio_url": str(pron.get("audio_url", ""))[:500]
                if pron.get("audio_url")
                else None,
                "dialect": str(pron.get("dialect", ""))[:50]
                if pron.get("dialect")
                else None,
            }
        )
    cleaned["pronunciations"] = pronunciations

    return cleaned


def create_db_entry(session: Session, data: Dict[str, Any]) -> Optional[Entry]:
    """Create database entry from validated data."""
    try:
        # Create main entry
        entry = Entry(
            title=data["title"],
            language=data["language"],
            part_of_speech=data["part_of_speech"],
            etymology=data["etymology"],
        )

        # Add senses
        for sense_data in data["senses"]:
            sense = Sense(
                definition=sense_data["definition"], notes=sense_data["notes"]
            )

            # Add examples
            for example_data in sense_data["examples"]:
                example = Example(
                    text=example_data["text"], translation=example_data["translation"]
                )
                sense.examples.append(example)

            # Add translations
            for trans_data in sense_data["translations"]:
                translation = Translation(
                    language=trans_data["language"],
                    text=trans_data["text"],
                    notes=trans_data["notes"],
                )
                sense.translations.append(translation)

            entry.senses.append(sense)

        # Add forms
        for form_data in data["forms"]:
            form = Form(form=form_data["form"], tags=form_data["tags"])
            entry.forms.append(form)

        # Add pronunciations
        for pron_data in data["pronunciations"]:
            pronunciation = Pronunciation(
                text=pron_data["text"],
                audio_url=pron_data["audio_url"],
                dialect=pron_data["dialect"],
            )
            entry.pronunciations.append(pronunciation)

        session.add(entry)
        return entry

    except Exception as e:
        logging.error(f"Error creating entry {data['title']}: {str(e)}")
        session.rollback()
        return None


def populate_database(input_path: Path, output_path: Path, force: bool = False):
    """Populate the database from a JSONL file.

    Args:
        input_path: Path to input JSONL file
        output_path: Path to output SQLite database file
        force: If True, overwrite existing database file. If False, raise error if file exists.
    """
    # Check if database exists
    if output_path.exists():
        if force:
            output_path.unlink()
            logging.info(f"Removed existing database: {output_path}")
        else:
            raise FileExistsError(
                f"Database file already exists: {output_path}. Use --force to overwrite."
            )

    # Initialize database
    engine = create_engine(f"sqlite:///{output_path}")
    Base.metadata.create_all(engine)

    # Process JSONL file

    processed = 0
    skipped = 0

    with Session(engine) as session:
        # Get total lines efficiently using wc -l
        import subprocess

        result = subprocess.run(
            ["wc", "-l", str(input_path)], capture_output=True, text=True
        )
        total_lines = int(result.stdout.split()[0])

        with open(input_path, "r", encoding="utf-8") as f:
            pbar = tqdm(enumerate(f, 1), total=total_lines, desc="Processing entries")
            for line_num, line in pbar:
                try:
                    # Parse JSON line
                    data = json.loads(line)

                    # Validate and clean data
                    cleaned_data = validate_entry(data)
                    if not cleaned_data:
                        skipped += 1
                        continue

                    # Create database entry
                    entry = create_db_entry(session, cleaned_data)
                    if entry:
                        processed += 1
                    else:
                        skipped += 1

                    # Commit every 1000 entries
                    if processed % 1000 == 0:
                        session.commit()
                        logging.info(
                            f"Processed {processed} entries (skipped {skipped})"
                        )

                except json.JSONDecodeError:
                    logging.error(f"Invalid JSON on line {line_num}")
                    skipped += 1
                except Exception as e:
                    logging.error(f"Error processing line {line_num}: {str(e)}")
                    skipped += 1
                    session.rollback()

        # Final commit
        session.commit()

    logging.info(
        f"Import complete. Processed {processed} entries, skipped {skipped} entries"
    )


if __name__ == "__main__":
    # Example usage when run directly
    input_path = Path("resources/wiktextract-en.jsonl")
    output_path = Path("resources/wiktextract-en.db")
    populate_database(input_path, output_path)
