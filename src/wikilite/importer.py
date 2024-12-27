"""Module for importing Wiktionary data into SQLite database."""

from typing import Dict
from sqlalchemy.orm import Session

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
    """Handles importing Wiktionary data into SQLite database."""

    def __init__(self, session: Session):
        self.session = session
        self._category_cache: Dict[str, Category] = {}
        self._topic_cache: Dict[str, Topic] = {}
        self._tag_cache: Dict[str, Tag] = {}
        self._word_cache: Dict[tuple, Word] = {}
        self._sense_cache: Dict[tuple, Sense] = {}

    def _get_category(self, name: str) -> Category:
        """Get or create a category."""
        if name not in self._category_cache:
            category = self.session.query(Category).filter_by(name=name).first()
            if not category:
                category = Category(name=name)
                self.session.add(category)
            self._category_cache[name] = category
        return self._category_cache[name]

    def _get_topic(self, name: str) -> Topic:
        """Get or create a topic."""
        if name not in self._topic_cache:
            topic = self.session.query(Topic).filter_by(name=name).first()
            if not topic:
                topic = Topic(name=name)
                self.session.add(topic)
            self._topic_cache[name] = topic
        return self._topic_cache[name]

    def _get_tag(self, name: str) -> Tag:
        """Get or create a tag."""
        if name not in self._tag_cache:
            tag = self.session.query(Tag).filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                self.session.add(tag)
            self._tag_cache[name] = tag
        return self._tag_cache[name]

    def _get_word(self, entry: WordEntry) -> Word:
        """Get or create a word entry."""
        key = (entry.word, entry.pos, entry.lang_code, entry.etymology_number)
        if key not in self._word_cache:
            word = Word(
                word=entry.word,
                pos=entry.pos,
                lang=entry.lang,
                lang_code=entry.lang_code,
                etymology_text=entry.etymology_text,
                etymology_number=entry.etymology_number,
                wiktionary_id=entry.wiktionary,
            )
            self._word_cache[key] = word
            self.session.add(word)
        return self._word_cache[key]

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
            self.session.add(form)

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
                # Create target word and sense if needed
                target_word = Word(
                    word=rel.word,
                    pos="unknown",  # We don't have this info in WordLinkage
                    lang="unknown",
                    lang_code="unknown",
                )
                target_sense = Sense(word=target_word)
                self.session.add(target_word)
                self.session.add(target_sense)

                # Create the relation
                relation = SenseRelation(
                    source=sense,
                    target=target_sense,
                    relation_type=rel_type,
                    topics=",".join(rel.topics) if rel.topics else None,
                    taxonomic=rel.taxonomic,
                    roman=rel.roman,
                )
                self.session.add(relation)

    def _process_sense(self, word: Word, word_sense: WordSense) -> Sense:
        """Process and create a word sense."""
        sense = Sense(word=word, english=word_sense.english)
        self.session.add(sense)

        # Add glosses
        for gloss_text in word_sense.glosses:
            gloss = Gloss(sense=sense, text=gloss_text, is_raw=False)
            self.session.add(gloss)

        for gloss_text in word_sense.raw_glosses:
            gloss = Gloss(sense=sense, text=gloss_text, is_raw=True)
            self.session.add(gloss)

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
            self.session.add(example)

        # Add tags
        sense.tags = [self._get_tag(tag) for tag in word_sense.tags]

        # Process semantic relationships
        self._process_sense_relations(sense, word_sense)

        return sense

    def import_entry(self, entry: WordEntry) -> None:
        """Import a single word entry into the database."""
        # Create or get the word
        word = self._get_word(entry)

        # Add categories
        for category_data in entry.categories:
            word.categories.append(self._get_category(category_data["name"]))

        # Add topics
        for topic_name in entry.topics:
            word.topics.append(self._get_topic(topic_name))

        # Process word forms
        self._process_word_forms(word, entry)

        # Process senses
        for word_sense in entry.senses:
            self._process_sense(word, word_sense)

        # Commit after each entry to avoid memory issues with large imports
        self.session.commit()
