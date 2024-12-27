"""SQLAlchemy models for Wiktionary data."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    ForeignKey,
    String,
    Text,
    DateTime,
    Enum as SQLEnum,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class LinkageType(Enum):
    """Types of word linkages."""

    DESCENDANTS = "descendants"
    SYNONYMS = "synonyms"
    ANTONYMS = "antonyms"
    HYPERNYMS = "hypernyms"
    HYPONYMS = "hyponyms"
    HOLONYMS = "holonyms"
    MERONYMS = "meronyms"
    DERIVED = "derived"
    RELATED = "related"
    COORDINATE_TERMS = "coordinate_terms"


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Entry(Base):
    """Model representing a Wiktionary entry."""

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    language: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    lang_code: Mapped[str] = mapped_column(
        String(10), index=True, nullable=False
    )  # e.g., 'en'

    # Add unique constraint across title, language, and lang_code
    __table_args__ = (
        UniqueConstraint("title", "language", "lang_code", name="uix_entry_title_lang"),
    )
    part_of_speech: Mapped[Optional[str]] = mapped_column(String(50))
    etymology_text: Mapped[Optional[str]] = mapped_column(Text)
    etymology_templates: Mapped[Optional[dict]] = mapped_column(
        JSON
    )  # Store template data as JSON
    etymology_number: Mapped[Optional[int]] = (
        mapped_column()
    )  # For words with multiple etymologies
    categories: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Store as comma-separated list
    topics: Mapped[Optional[str]] = mapped_column(Text)  # Store as comma-separated list
    wikidata: Mapped[Optional[str]] = mapped_column(String(50))  # Wikidata identifier
    wikipedia: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # Wikipedia page title
    head_templates: Mapped[Optional[dict]] = mapped_column(
        JSON
    )  # Store template data as JSON
    inflection_templates: Mapped[Optional[dict]] = mapped_column(
        JSON
    )  # Store template data as JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    senses: Mapped[List["Sense"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    forms: Mapped[List["Form"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    pronunciations: Mapped[List["Pronunciation"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    descendants: Mapped[List["Descendant"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )

    # Word linkages where this entry is the source
    source_linkages: Mapped[List["WordLinkage"]] = relationship(
        foreign_keys="[WordLinkage.source_id]",
        back_populates="source",
        cascade="all, delete-orphan",
    )

    # Word linkages where this entry is the target
    target_linkages: Mapped[List["WordLinkage"]] = relationship(
        foreign_keys="[WordLinkage.target_id]",
        back_populates="target",
        cascade="all, delete-orphan",
        overlaps="source_linkages",
    )


class Sense(Base):
    """Model representing a word sense/definition."""

    __tablename__ = "senses"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    raw_glosses: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Less cleaned version of glosses
    tags: Mapped[Optional[str]] = mapped_column(Text)  # Store as comma-separated list
    categories: Mapped[Optional[str]] = mapped_column(Text)  # Sense-specific categories
    topics: Mapped[Optional[str]] = mapped_column(Text)  # Sense-specific topics
    alt_of: Mapped[Optional[dict]] = mapped_column(JSON)  # Alternative forms
    form_of: Mapped[Optional[dict]] = mapped_column(JSON)  # Inflected forms
    senseid: Mapped[Optional[str]] = mapped_column(String(255))  # Textual identifiers
    wikidata: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # Sense-specific Wikidata
    wikipedia: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # Sense-specific Wikipedia
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entry: Mapped["Entry"] = relationship(back_populates="senses")
    examples: Mapped[List["Example"]] = relationship(
        back_populates="sense", cascade="all, delete-orphan"
    )
    translations: Mapped[List["Translation"]] = relationship(
        back_populates="sense", cascade="all, delete-orphan"
    )
    linkages: Mapped[List["WordLinkage"]] = relationship(
        back_populates="sense", cascade="all, delete-orphan"
    )


class Form(Base):
    """Model representing word forms (inflections, conjugations, etc.)."""

    __tablename__ = "forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    form: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[str] = mapped_column(String(255))  # e.g., plural, past_tense
    ipa: Mapped[Optional[str]] = mapped_column(String(255))  # IPA pronunciation
    roman: Mapped[Optional[str]] = mapped_column(String(255))  # Romanization
    source: Mapped[Optional[str]] = mapped_column(Text)  # Source information
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entry: Mapped["Entry"] = relationship(back_populates="forms")


class Example(Base):
    """Model representing usage examples."""

    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(primary_key=True)
    sense_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[Optional[str]] = mapped_column(Text)  # English translation
    ref: Mapped[Optional[str]] = mapped_column(Text)  # Source reference
    type: Mapped[Optional[str]] = mapped_column(String(50))  # example or quotation
    roman: Mapped[Optional[str]] = mapped_column(Text)  # Romanization
    note: Mapped[Optional[str]] = mapped_column(Text)  # English note
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sense: Mapped["Sense"] = relationship(back_populates="examples")


class Translation(Base):
    """Model representing translations."""

    __tablename__ = "translations"

    id: Mapped[int] = mapped_column(primary_key=True)
    sense_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)  # Language code
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    alt: Mapped[Optional[str]] = mapped_column(String(255))  # Alternative form
    roman: Mapped[Optional[str]] = mapped_column(String(255))  # Romanization
    note: Mapped[Optional[str]] = mapped_column(Text)  # Translation note
    sense_note: Mapped[Optional[str]] = mapped_column(Text)  # Sense clarification
    tags: Mapped[Optional[str]] = mapped_column(Text)  # Qualifiers
    taxonomic: Mapped[Optional[str]] = mapped_column(String(255))  # Taxonomic name
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sense: Mapped["Sense"] = relationship(back_populates="translations")


class Pronunciation(Base):
    """Model representing pronunciation data."""

    __tablename__ = "pronunciations"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    text: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # IPA or other notation
    ipa: Mapped[Optional[str]] = mapped_column(String(255))  # IPA pronunciation
    enpr: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # English pronunciation respelling
    audio: Mapped[Optional[str]] = mapped_column(String(255))  # Audio filename
    audio_ipa: Mapped[Optional[str]] = mapped_column(String(255))  # IPA for audio
    ogg_url: Mapped[Optional[str]] = mapped_column(String(500))  # OGG format URL
    mp3_url: Mapped[Optional[str]] = mapped_column(String(500))  # MP3 format URL
    homophones: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Store as comma-separated list
    hyphenation: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Store as comma-separated list
    tags: Mapped[Optional[str]] = mapped_column(String(255))  # e.g., UK, US
    text_note: Mapped[Optional[str]] = mapped_column(Text)  # Text associated with audio
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entry: Mapped["Entry"] = relationship(back_populates="pronunciations")


class WordLinkage(Base):
    """Model representing relationships between words (synonyms, antonyms, etc.)."""

    __tablename__ = "word_linkages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    target_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    linkage_type: Mapped[LinkageType] = mapped_column(SQLEnum(LinkageType))
    sense_id: Mapped[Optional[int]] = mapped_column(ForeignKey("senses.id"))
    alt: Mapped[Optional[str]] = mapped_column(String(255))  # Alternative form
    roman: Mapped[Optional[str]] = mapped_column(String(255))  # Romanization
    sense_note: Mapped[Optional[str]] = mapped_column(Text)  # Sense clarification
    tags: Mapped[Optional[str]] = mapped_column(String(255))  # Qualifiers
    topics: Mapped[Optional[str]] = mapped_column(String(255))  # Topic descriptors
    taxonomic: Mapped[Optional[str]] = mapped_column(String(255))  # Taxonomic name
    notes: Mapped[Optional[str]] = mapped_column(Text)  # Additional context
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    source: Mapped["Entry"] = relationship(
        foreign_keys=[source_id], back_populates="source_linkages"
    )
    target: Mapped["Entry"] = relationship(
        foreign_keys=[target_id], back_populates="target_linkages"
    )
    sense: Mapped[Optional["Sense"]] = relationship(back_populates="linkages")


class Descendant(Base):
    """Model representing word descendants."""

    __tablename__ = "descendants"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    depth: Mapped[int] = mapped_column()  # Level of indentation
    templates: Mapped[Optional[dict]] = mapped_column(JSON)  # Template data as JSON
    text: Mapped[str] = mapped_column(Text)  # Expanded and cleaned text
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entry: Mapped["Entry"] = relationship(back_populates="descendants")
