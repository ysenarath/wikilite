"""Script to populate SQLite database from Wiktionary JSONL data."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, exc as sqlalchemy_exceptions
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
    WordLinkage,
    Descendant,
    LinkageType,
)


# Initialize logger
logger = logging.getLogger(__name__)


def setup_logger() -> logging.Logger:
    # Only configure if no handlers exist
    if not logger.handlers:
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Configure logger
        logger.setLevel(logging.INFO)

        # File handler
        file_handler = logging.FileHandler(logs_dir / "import.log", mode="w")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )

        # Add handlers
        logger.addHandler(file_handler)

    return logger


# Configure logger
setup_logger()


def clean_list_to_string(
    items: Optional[List[str]], max_length: Optional[int] = None
) -> Optional[str]:
    """Convert list to comma-separated string with optional length limit."""
    if not items:
        return None
    result = ",".join(str(item) for item in items)
    if max_length:
        result = result[:max_length]
    return result


def validate_entry(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate and clean entry data.

    Returns:
        Dict with cleaned data if valid, None if invalid
    """
    # Required fields
    if not all(key in data for key in ["word", "lang", "lang_code"]):
        logger.error(f"Missing required fields in entry: {data.get('word', 'UNKNOWN')}")
        return None

    # Clean and validate data
    cleaned = {
        "title": str(data["word"])[:255],
        "language": str(data["lang"])[:50],
        "lang_code": str(data["lang_code"])[:10],
        "part_of_speech": str(data.get("pos", ""))[:50] if data.get("pos") else None,
        "etymology_text": data.get("etymology_text"),
        "etymology_templates": data.get("etymology_templates"),
        "etymology_number": data.get("etymology_number"),
        "categories": clean_list_to_string(data.get("categories")),
        "topics": clean_list_to_string(data.get("topics")),
        "wikidata": str(data.get("wikidata", ""))[:50]
        if data.get("wikidata")
        else None,
        "wikipedia": str(data.get("wikipedia", ""))[:255]
        if data.get("wikipedia")
        else None,
        "head_templates": data.get("head_templates"),
        "inflection_templates": data.get("inflection_templates"),
    }

    # Validate and process senses
    senses = []
    for sense_data in data.get("senses", []):
        if not sense_data.get("glosses"):
            logger.warning(f"Skipping sense without gloss for word: {data['word']}")
            continue

        sense = {
            "definition": " | ".join(sense_data["glosses"]),
            "raw_glosses": " | ".join(sense_data.get("raw_glosses", [])),
            "tags": clean_list_to_string(sense_data.get("tags")),
            "categories": clean_list_to_string(sense_data.get("categories")),
            "topics": clean_list_to_string(sense_data.get("topics")),
            "alt_of": sense_data.get("alt_of"),
            "form_of": sense_data.get("form_of"),
            "senseid": str(sense_data.get("senseid", ""))[:255]
            if sense_data.get("senseid")
            else None,
            "wikidata": str(sense_data.get("wikidata", ""))[:50]
            if sense_data.get("wikidata")
            else None,
            "wikipedia": str(sense_data.get("wikipedia", ""))[:255]
            if sense_data.get("wikipedia")
            else None,
            "notes": sense_data.get("notes"),
            "examples": [],
            "translations": [],
        }

        # Process examples
        for example in sense_data.get("examples", []):
            if isinstance(example, dict):
                sense["examples"].append(
                    {
                        "text": example.get("text", ""),
                        "translation": example.get("english"),  # english field in docs
                        "ref": example.get("ref"),
                        "type": example.get("type"),
                        "roman": example.get("roman"),
                        "note": example.get("note"),
                    }
                )

        # Process translations
        for trans in sense_data.get("translations", []):
            if isinstance(trans, dict):
                sense["translations"].append(
                    {
                        "language": trans.get("lang", "")[:50],
                        "code": trans.get("code", "")[:10],
                        "word": trans.get("word", "")[:255],
                        "alt": trans.get("alt"),
                        "roman": trans.get("roman"),
                        "note": trans.get("note"),
                        "sense_note": trans.get("sense"),
                        "tags": clean_list_to_string(trans.get("tags")),
                        "taxonomic": trans.get("taxonomic"),
                    }
                )

        senses.append(sense)

    if not senses:
        logger.warning(f"No valid senses found for word: {data['word']}")
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
                "tags": clean_list_to_string(form_data.get("tags"), 255),
                "ipa": form_data.get("ipa"),
                "roman": form_data.get("roman"),
                "source": form_data.get("source"),
            }
        )
    cleaned["forms"] = forms

    # Process pronunciations
    pronunciations = []
    for pron in data.get("sounds", []):  # 'sounds' in docs
        pronunciations.append(
            {
                "text": str(pron.get("text", ""))[:255],  # Use text as primary field
                "ipa": pron.get("ipa"),
                "enpr": pron.get("enpr"),
                "audio": pron.get("audio"),
                "audio_ipa": pron.get("audio-ipa"),  # hyphen in docs
                "ogg_url": pron.get("ogg_url"),
                "mp3_url": pron.get("mp3_url"),
                "homophones": clean_list_to_string(pron.get("homophones")),
                "hyphenation": clean_list_to_string(pron.get("hyphenation")),
                "tags": clean_list_to_string(pron.get("tags"), 255),
                "text_note": None,  # Don't duplicate text field
            }
        )
    cleaned["pronunciations"] = pronunciations

    # Process descendants
    descendants = []
    for desc in data.get("descendants", []):
        if isinstance(desc, dict):
            descendants.append(
                {
                    "depth": desc.get("depth", 0),
                    "templates": desc.get("templates"),
                    "text": desc.get("text", ""),
                }
            )
    cleaned["descendants"] = descendants

    # Process word linkages
    linkages = []
    for linkage_type in [
        "synonyms",
        "antonyms",
        "hypernyms",
        "hyponyms",
        "holonyms",
        "meronyms",
        "derived",
        "related",
        "coordinate_terms",
    ]:
        for linkage in data.get(linkage_type, []):
            if isinstance(linkage, dict) and linkage.get("word"):
                linkages.append(
                    {
                        "type": linkage_type,
                        "word": linkage["word"],
                        "alt": linkage.get("alt"),
                        "roman": linkage.get("roman"),
                        "sense_note": linkage.get("sense"),
                        "tags": clean_list_to_string(linkage.get("tags"), 255),
                        "topics": clean_list_to_string(linkage.get("topics"), 255),
                        "taxonomic": linkage.get("taxonomic"),
                        "notes": linkage.get("notes"),
                    }
                )
    cleaned["linkages"] = linkages

    return cleaned


def create_db_entry(session: Session, data: Dict[str, Any]) -> Optional[Entry]:
    """Create database entry from validated data."""
    try:
        # Create main entry
        entry = Entry(
            title=data["title"],
            language=data["language"],
            lang_code=data["lang_code"],
            part_of_speech=data["part_of_speech"],
            etymology_text=data["etymology_text"],
            etymology_templates=data["etymology_templates"],
            etymology_number=data["etymology_number"],
            categories=data["categories"],
            topics=data["topics"],
            wikidata=data["wikidata"],
            wikipedia=data["wikipedia"],
            head_templates=data["head_templates"],
            inflection_templates=data["inflection_templates"],
        )

        # Add senses
        for sense_data in data["senses"]:
            sense = Sense(
                definition=sense_data["definition"],
                raw_glosses=sense_data["raw_glosses"],
                tags=sense_data["tags"],
                categories=sense_data["categories"],
                topics=sense_data["topics"],
                alt_of=sense_data["alt_of"],
                form_of=sense_data["form_of"],
                senseid=sense_data["senseid"],
                wikidata=sense_data["wikidata"],
                wikipedia=sense_data["wikipedia"],
                notes=sense_data["notes"],
            )

            # Add examples
            for example_data in sense_data["examples"]:
                example = Example(
                    text=example_data["text"],
                    translation=example_data["translation"],
                    ref=example_data["ref"],
                    type=example_data["type"],
                    roman=example_data["roman"],
                    note=example_data["note"],
                )
                sense.examples.append(example)

            # Add translations
            for trans_data in sense_data["translations"]:
                translation = Translation(
                    language=trans_data["language"],
                    code=trans_data["code"],
                    word=trans_data["word"],
                    alt=trans_data["alt"],
                    roman=trans_data["roman"],
                    note=trans_data["note"],
                    sense_note=trans_data["sense_note"],
                    tags=trans_data["tags"],
                    taxonomic=trans_data["taxonomic"],
                )
                sense.translations.append(translation)

            entry.senses.append(sense)

        # Add forms
        for form_data in data["forms"]:
            form = Form(
                form=form_data["form"],
                tags=form_data["tags"],
                ipa=form_data["ipa"],
                roman=form_data["roman"],
                source=form_data["source"],
            )
            entry.forms.append(form)

        # Add pronunciations
        for pron_data in data["pronunciations"]:
            pronunciation = Pronunciation(
                text=pron_data["text"],
                ipa=pron_data["ipa"],
                enpr=pron_data["enpr"],
                audio=pron_data["audio"],
                audio_ipa=pron_data["audio_ipa"],
                ogg_url=pron_data["ogg_url"],
                mp3_url=pron_data["mp3_url"],
                homophones=pron_data["homophones"],
                hyphenation=pron_data["hyphenation"],
                tags=pron_data["tags"],
                text_note=pron_data["text_note"],
            )
            entry.pronunciations.append(pronunciation)

        # Add descendants
        for desc_data in data["descendants"]:
            descendant = Descendant(
                depth=desc_data["depth"],
                templates=desc_data["templates"],
                text=desc_data["text"],
            )
            entry.descendants.append(descendant)

        # Add word linkages
        for linkage_data in data["linkages"]:
            # Get or create target entry
            target_entry = (
                session.query(Entry)
                .filter_by(
                    title=linkage_data["word"],
                    language=data["language"],
                    lang_code=data["lang_code"],
                )
                .first()
            )

            if not target_entry:
                # Create a placeholder entry that will be populated later
                target_entry = Entry(
                    title=linkage_data["word"],
                    language=data["language"],
                    lang_code=data["lang_code"],
                    part_of_speech=None,  # Minimal required fields only
                )
                session.add(target_entry)
                session.flush()

            # Create and add the linkage
            linkage = WordLinkage(
                source=entry,  # This will automatically handle source_linkages
                target=target_entry,  # This will automatically handle target_linkages
                linkage_type=LinkageType[linkage_data["type"].upper()],
                alt=linkage_data["alt"],
                roman=linkage_data["roman"],
                sense_note=linkage_data["sense_note"],
                tags=linkage_data["tags"],
                topics=linkage_data["topics"],
                taxonomic=linkage_data["taxonomic"],
                notes=linkage_data["notes"],
            )
            session.add(linkage)
            session.flush()  # Ensure linkage is properly saved

        session.add(entry)
        return entry

    except sqlalchemy_exceptions.IntegrityError as e:
        # Handle unique constraint violations
        logger.warning(
            f"Duplicate entry found for {data['title']} in {data['language']}, updating existing entry"
        )
        session.rollback()

        # Get existing entry and update it
        existing_entry = (
            session.query(Entry)
            .filter_by(
                title=data["title"],
                language=data["language"],
                lang_code=data["lang_code"],
            )
            .first()
        )

        if existing_entry:
            # Clear existing relationships
            existing_entry.senses.clear()
            existing_entry.forms.clear()
            existing_entry.pronunciations.clear()
            existing_entry.descendants.clear()
            existing_entry.source_linkages.clear()

            # Update fields
            for key, value in data.items():
                if hasattr(existing_entry, key):
                    setattr(existing_entry, key, value)

            session.flush()
            return existing_entry
        return None
    except Exception as e:
        logger.error(f"Error creating entry {data['title']}: {str(e)}")
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
            logger.info(f"Removed existing database: {output_path}")
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
                        logger.info(
                            f"Processed {processed} entries (skipped {skipped})"
                        )

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON on line {line_num}")
                    skipped += 1
                except Exception as e:
                    logger.error(f"Error processing line {line_num}: {str(e)}")
                    skipped += 1
                    session.rollback()

        # Final commit
        session.commit()

    logger.info(
        f"Import complete. Processed {processed} entries, skipped {skipped} entries"
    )


if __name__ == "__main__":
    # Example usage when run directly
    input_path = Path("resources/wiktextract-en.jsonl")
    output_path = Path("resources/wiktextract-en.db")
    populate_database(input_path, output_path)
