"""Module for batch importing Wiktionary data into SQLite database."""

from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from .utils.wiktextract import WordEntry, WordSense, WordLinkage
from .models import (
    Word,
    Sense,
    SenseRelation,
    Gloss,
    Example,
    WordForm,
    Category,
    Topic,
    Tag,
)


class WiktionaryImporter:
    """Handles batch importing of Wiktionary data into SQLite database."""

    def __init__(self, session: Session, batch_size: int = 1000):
        """Initialize the batch importer.

        Args:
            session: SQLAlchemy session
            batch_size: Number of entries to process before committing
        """
        self.session = session
        self.batch_size = batch_size

        # Persistent caches
        self._category_cache: Dict[str, Category] = {}
        self._topic_cache: Dict[str, Topic] = {}
        self._tag_cache: Dict[str, Tag] = {}

        # Batch collection
        self._pending_words: List[Word] = []
        self._pending_senses: List[Sense] = []
        self._pending_glosses: List[Gloss] = []
        self._pending_examples: List[Example] = []
        self._pending_forms: List[WordForm] = []
        self._pending_relations: List[SenseRelation] = []

        # Track processed entries
        self._entries_processed = 0

        # Pre-load existing records
        self._preload_caches()

    def _preload_caches(self) -> None:
        """Pre-load existing categories, topics, and tags into cache."""
        # Load categories
        for category in self.session.execute(select(Category)).scalars():
            self._category_cache[category.name] = category

        # Load topics
        for topic in self.session.execute(select(Topic)).scalars():
            self._topic_cache[topic.name] = topic

        # Load tags
        for tag in self.session.execute(select(Tag)).scalars():
            self._tag_cache[tag.name] = tag

    def _get_category(self, name: str) -> Category:
        """Get or create a category."""
        if name not in self._category_cache:
            category = Category(name=name)
            self.session.add(category)
            self._category_cache[name] = category
        return self._category_cache[name]

    def _get_topic(self, name: str) -> Topic:
        """Get or create a topic."""
        if name not in self._topic_cache:
            topic = Topic(name=name)
            self.session.add(topic)
            self._topic_cache[name] = topic
        return self._topic_cache[name]

    def _get_tag(self, name: str) -> Tag:
        """Get or create a tag."""
        if name not in self._tag_cache:
            tag = Tag(name=name)
            self.session.add(tag)
            self._tag_cache[name] = tag
        return self._tag_cache[name]

    def _process_word(self, entry: WordEntry) -> Word:
        """Process and create a word entry."""
        word = Word(
            word=entry.word,
            pos=entry.pos,
            lang=entry.lang,
            lang_code=entry.lang_code,
            etymology_text=entry.etymology_text,
            etymology_number=entry.etymology_number,
            wiktionary_id=entry.wiktionary,
        )

        # Add categories and topics
        word.categories = [self._get_category(cat["name"]) for cat in entry.categories]
        word.topics = [self._get_topic(topic) for topic in entry.topics]

        self._pending_words.append(word)
        return word

    def _process_word_forms(self, word: Word, entry: WordEntry) -> None:
        """Process and create word forms."""
        for form_data in entry.forms:
            form = WordForm(
                word=word,
                form=form_data["form"],
                ipa=form_data.get("ipa"),
                roman=form_data.get("roman"),
                source=form_data.get("source"),
            )
            if "tags" in form_data:
                form.tags = [self._get_tag(tag) for tag in form_data["tags"]]
            self._pending_forms.append(form)

    def _process_sense_relations(self, sense: Sense, word_sense: WordSense) -> None:
        """Process semantic relationships for a sense."""
        relation_types = {
            "synonyms": "synonym",
            "antonyms": "antonym",
            "hypernyms": "hypernym",
            "hyponyms": "hyponym",
            "meronyms": "meronym",
            "holonyms": "holonym",
        }

        for attr, rel_type in relation_types.items():
            relations: list[WordLinkage] = getattr(word_sense, attr, [])
            for rel in relations:
                # Create target word and sense
                target_word = Word(
                    word=rel.word,
                    pos="unknown",
                    lang="unknown",
                    lang_code="unknown",
                )
                self._pending_words.append(target_word)

                target_sense = Sense(word=target_word)
                self._pending_senses.append(target_sense)

                # Create the relation
                relation = SenseRelation(
                    source=sense,
                    target=target_sense,
                    relation_type=rel_type,
                    topics=",".join(rel.topics) if rel.topics else None,
                    taxonomic=rel.taxonomic,
                    roman=rel.roman,
                )
                self._pending_relations.append(relation)

    def _process_sense(self, word: Word, word_sense: WordSense) -> None:
        """Process and create a word sense."""
        sense = Sense(word=word, english=word_sense.english)
        self._pending_senses.append(sense)

        # Add glosses
        for gloss_text in word_sense.glosses:
            gloss = Gloss(sense=sense, text=gloss_text, is_raw=False)
            self._pending_glosses.append(gloss)

        for gloss_text in word_sense.raw_glosses:
            gloss = Gloss(sense=sense, text=gloss_text, is_raw=True)
            self._pending_glosses.append(gloss)

        # Add examples
        for example_data in word_sense.examples:
            example = Example(
                sense=sense,
                text=example_data.text,
                ref=example_data.ref,
                english=example_data.english,
                type=example_data.type,
                roman=example_data.roman,
                note=example_data.note,
            )
            self._pending_examples.append(example)

        # Add tags
        sense.tags = [self._get_tag(tag) for tag in word_sense.tags]

        # Process semantic relationships
        self._process_sense_relations(sense, word_sense)

    def import_word(self, entry: WordEntry) -> None:
        """Import a single word entry into the batch."""
        # Process the main word
        word = self._process_word(entry)

        # Process word forms
        self._process_word_forms(word, entry)

        # Process senses
        for word_sense in entry.senses:
            self._process_sense(word, word_sense)

        self._entries_processed += 1

        # Commit batch if we've reached batch_size
        if self._entries_processed % self.batch_size == 0:
            self.flush_batch()

    def flush_batch(self) -> None:
        """Flush the current batch to the database."""
        if not any(
            [
                self._pending_words,
                self._pending_senses,
                self._pending_glosses,
                self._pending_examples,
                self._pending_forms,
                self._pending_relations,
            ]
        ):
            return

        try:
            # First save all words to get their IDs
            for word in self._pending_words:
                self.session.add(word)
            self.session.flush()

            # Now we can set word_ids on senses
            for sense in self._pending_senses:
                if sense.word_id is None and sense.word is not None:
                    sense.word_id = sense.word.id

            # Save senses to get their IDs
            for sense in self._pending_senses:
                self.session.add(sense)
            self.session.flush()

            # Set sense_ids on glosses and examples
            for gloss in self._pending_glosses:
                if gloss.sense_id is None and gloss.sense is not None:
                    gloss.sense_id = gloss.sense.id

            for example in self._pending_examples:
                if example.sense_id is None and example.sense is not None:
                    example.sense_id = example.sense.id

            # Set word_ids on forms
            for form in self._pending_forms:
                if form.word_id is None and form.word is not None:
                    form.word_id = form.word.id

            # Set sense ids on relations
            for relation in self._pending_relations:
                if relation.source_id is None and relation.source is not None:
                    relation.source_id = relation.source.id
                if relation.target_id is None and relation.target is not None:
                    relation.target_id = relation.target.id

            # Now we can bulk save the remaining objects
            self.session.bulk_save_objects(self._pending_glosses)
            self.session.bulk_save_objects(self._pending_examples)
            self.session.bulk_save_objects(self._pending_forms)
            self.session.bulk_save_objects(self._pending_relations)

            # Commit everything
            self.session.commit()

        finally:
            # Clear pending lists
            self._pending_words = []
            self._pending_senses = []
            self._pending_glosses = []
            self._pending_examples = []
            self._pending_forms = []
            self._pending_relations = []

    def finalize(self) -> None:
        """Finalize the import by flushing any remaining entries."""
        self.flush_batch()
