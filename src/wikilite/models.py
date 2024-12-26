"""SQLAlchemy models for Wiktionary data."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Entry(Base):
    """Model representing a Wiktionary entry."""

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    language: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    part_of_speech: Mapped[Optional[str]] = mapped_column(String(50))
    etymology: Mapped[Optional[str]] = mapped_column(Text)
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


class Sense(Base):
    """Model representing a word sense/definition."""

    __tablename__ = "senses"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    definition: Mapped[str] = mapped_column(Text, nullable=False)
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


class Form(Base):
    """Model representing word forms (inflections, conjugations, etc.)."""

    __tablename__ = "forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    form: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[str] = mapped_column(String(255))  # e.g., plural, past_tense
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entry: Mapped["Entry"] = relationship(back_populates="forms")


class Example(Base):
    """Model representing usage examples."""

    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(primary_key=True)
    sense_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sense: Mapped["Sense"] = relationship(back_populates="examples")


class Translation(Base):
    """Model representing translations."""

    __tablename__ = "translations"

    id: Mapped[int] = mapped_column(primary_key=True)
    sense_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
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
    audio_url: Mapped[Optional[str]] = mapped_column(String(500))
    dialect: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., UK, US
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    entry: Mapped["Entry"] = relationship(back_populates="pronunciations")
