from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import create_engine as create_engine_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from wikilite.models import Base, Example, Triplet, Word
from wikilite.utils import wiktextract
from wikilite.utils.wiktextract import get_relations, singularize_relation


def create_engine(path: Path | str | None = None, create_all: bool = True) -> Engine:
    """Initialize the database and create all tables."""
    engine = create_engine_(f"sqlite:///{path}")
    if create_all:
        Base.metadata.create_all(engine)
    return engine


def _import_words(inst: WikiLite, data: List[Tuple[str, Dict[str, List[str]]]]) -> None:
    """Import words and examples into the database."""
    BATCH_SIZE = 100_000
    Session = sessionmaker(bind=inst.engine)

    with Session() as session:
        # Initialize word mapping
        word_map: Dict[str, List[Word]] = {}

        # Process words in batches
        word_batch: List[Word] = []
        for word_str, definitions in tqdm(data, desc="Importing words"):
            for definition in definitions:
                word_obj = Word(word=word_str, definition=definition)
                word_batch.append(word_obj)
                word_map.setdefault(word_str, []).append(word_obj)

                if len(word_batch) >= BATCH_SIZE:
                    session.add_all(word_batch)
                    session.flush()  # Flush to get IDs but don't commit yet
                    word_batch = []

        # Add remaining words
        if word_batch:
            session.add_all(word_batch)
            session.flush()

        # Process examples in batches
        example_batch: List[Example] = []
        for word_str, definitions in tqdm(data, desc="Importing examples"):
            word_objs = word_map.get(word_str, [])
            if not word_objs:
                continue

            for word_obj, (definition, examples) in zip(word_objs, definitions.items()):
                for example_text in examples:
                    example = Example(word=word_obj, example=example_text)
                    example_batch.append(example)

                    if len(example_batch) >= BATCH_SIZE:
                        session.add_all(example_batch)
                        session.flush()
                        example_batch = []

        # Add remaining examples
        if example_batch:
            session.add_all(example_batch)

        session.commit()


def _import_triples(inst: WikiLite, triples: Set[Tuple[str, str, str]]) -> None:
    """Import triples into the database."""
    BATCH_SIZE = 100_000
    Session = sessionmaker(bind=inst.engine)

    with Session() as session:
        # Get all words and create a mapping
        word_map: Dict[str, List[Word]] = {}
        print("Loading words for triplet mapping...")
        for word_obj in tqdm(session.query(Word).all(), desc="Loading words"):
            word_map.setdefault(word_obj.word, []).append(word_obj)

        # Process triplets in batches
        triplet_batch: List[Triplet] = []
        for subject_str, predicate, object_str in tqdm(
            triples, desc="Importing triplets"
        ):
            subject_objs = word_map.get(subject_str, [])
            object_objs = word_map.get(object_str, [])

            # Create triplets for all combinations
            for subject_obj in subject_objs:
                for object_obj in object_objs:
                    triplet = Triplet(
                        subject=subject_obj, predicate=predicate, object=object_obj
                    )
                    triplet_batch.append(triplet)

                    if len(triplet_batch) >= BATCH_SIZE:
                        session.add_all(triplet_batch)
                        session.flush()
                        triplet_batch = []

        # Add remaining triplets
        if triplet_batch:
            session.add_all(triplet_batch)

        # Commit all changes
        session.commit()


def drop_all(engine: Engine) -> None:
    """Delete all data from the database."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


class WikiLite:
    def __init__(self, name_or_path: str):
        # check if the path is a directory
        if Path(name_or_path).is_dir():
            path = Path(name_or_path)
        else:
            path = Path.home() / ".cache" / "wikilite" / name_or_path
            if not path.exists():
                path.mkdir(parents=True)
        self.engine = create_engine(path / "data.db", create_all=True)

    @classmethod
    def from_jsonl(cls, path: Path | str, name: Optional[str] = None) -> WikiLite:
        """Create a new WikiLite instance from a JSONL file."""
        path = Path(path)
        self = cls(name or path.name)
        drop_all(self.engine)
        # word -> definition -> [examples]
        data: Dict[str, Dict[str, list]] = {}
        triples = set()
        for entry in wiktextract.load(path):
            relations = get_relations(entry)
            for rel, links in relations.items():
                for link in links:
                    rel = singularize_relation(rel)
                    triple = entry.word, rel, link.word
                    triples.add(triple)
            for sense in entry.senses:
                try:
                    definition = sense.definition
                except ValueError:
                    continue  # skip senses without definition
                if entry.word not in data:
                    data[entry.word] = {}
                if definition not in data[entry.word]:
                    data[entry.word][definition] = []
                data[entry.word][definition].extend(
                    [e.text for e in sense.examples if e.text]
                )
        # words in triples
        words = {w for w, _, _ in triples} | {w for _, _, w in triples}
        # words in data
        words = words.intersection(data.keys())
        # filter data
        data = [(w, d) for w, d in data.items() if w in words]
        # filter triples
        triples = {t for t in triples if t[0] in words or t[2] in words}
        # add words to the database
        _import_words(self, data)
        # add triples to the database
        _import_triples(self, triples)
        return self
