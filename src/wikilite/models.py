from __future__ import annotations

from sqlite3 import Connection as SQLite3Connection
from typing import List

from sqlalchemy import ForeignKey, String, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Enable foreign key support for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Create base class with naming convention
class Base(DeclarativeBase):
    pass


class Word(Base):
    """A word with its definition and relationships."""

    __tablename__ = "word"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(length=255), nullable=False, index=True)
    definition: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships with proper type hints
    examples: Mapped[List["Example"]] = relationship(
        back_populates="word", cascade="all, delete-orphan", lazy="write_only"
    )
    subject_triplets: Mapped[List["Triplet"]] = relationship(
        foreign_keys="[Triplet.subject_id]", back_populates="subject", lazy="write_only"
    )
    object_triplets: Mapped[List["Triplet"]] = relationship(
        foreign_keys="[Triplet.object_id]", back_populates="object", lazy="write_only"
    )


class Example(Base):
    """An example usage of a word."""

    __tablename__ = "example"

    id: Mapped[int] = mapped_column(primary_key=True)
    word_id: Mapped[int] = mapped_column(
        ForeignKey("word.id", ondelete="CASCADE"), nullable=False, index=True
    )
    example: Mapped[str] = mapped_column(String, nullable=False)

    # Relationship with proper type hint
    word: Mapped["Word"] = relationship(back_populates="examples", lazy="joined")


class Triplet(Base):
    """A semantic relationship between two words."""

    __tablename__ = "triplet"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("word.id", ondelete="CASCADE"), nullable=False, index=True
    )
    predicate: Mapped[str] = mapped_column(String(length=255), nullable=False)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("word.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships with proper type hints
    subject: Mapped["Word"] = relationship(
        foreign_keys=[subject_id], back_populates="subject_triplets", lazy="joined"
    )
    object: Mapped["Word"] = relationship(
        foreign_keys=[object_id], back_populates="object_triplets", lazy="joined"
    )
