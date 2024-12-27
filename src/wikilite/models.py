"""SQLAlchemy models for wikilite."""
from typing import List
from sqlalchemy import String, Integer, ForeignKey, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Association tables for many-to-many relationships
word_category = Table(
    "word_category",
    Base.metadata,
    Column("word_id", Integer, ForeignKey("words.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id"), primary_key=True),
)

word_topic = Table(
    "word_topic",
    Base.metadata,
    Column("word_id", Integer, ForeignKey("words.id"), primary_key=True),
    Column("topic_id", Integer, ForeignKey("topics.id"), primary_key=True),
)

sense_tag = Table(
    "sense_tag",
    Base.metadata,
    Column("sense_id", Integer, ForeignKey("senses.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)

word_form_tag = Table(
    "word_form_tag",
    Base.metadata,
    Column("word_form_id", Integer, ForeignKey("word_forms.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Category(Base):
    """Model for word categories."""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Topic(Base):
    """Model for linguistic topics."""
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Tag(Base):
    """Model for linguistic tags."""
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class WordForm(Base):
    """Model for word forms (inflections, variants)."""
    __tablename__ = "word_forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"))
    form: Mapped[str] = mapped_column(String(255))
    ipa: Mapped[str | None] = mapped_column(String, nullable=True)
    roman: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)

    word: Mapped["Word"] = relationship(back_populates="forms")
    tags: Mapped[List[Tag]] = relationship(secondary=word_form_tag)


class Word(Base):
    """Main word entry model."""
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(255))
    pos: Mapped[str] = mapped_column(String(50))  # part of speech
    lang: Mapped[str] = mapped_column(String(100))
    lang_code: Mapped[str] = mapped_column(String(10))
    etymology_text: Mapped[str | None] = mapped_column(String, nullable=True)
    etymology_number: Mapped[int] = mapped_column(default=0)
    wiktionary_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    senses: Mapped[List["Sense"]] = relationship(back_populates="word")
    forms: Mapped[List[WordForm]] = relationship(back_populates="word")
    categories: Mapped[List[Category]] = relationship(secondary=word_category)
    topics: Mapped[List[Topic]] = relationship(secondary=word_topic)


class Sense(Base):
    """Word sense/definition model."""
    __tablename__ = "senses"

    id: Mapped[int] = mapped_column(primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"))
    english: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    word: Mapped[Word] = relationship(back_populates="senses")
    glosses: Mapped[List["Gloss"]] = relationship(back_populates="sense")
    examples: Mapped[List["Example"]] = relationship(back_populates="sense")
    tags: Mapped[List[Tag]] = relationship(secondary=sense_tag)
    
    # Semantic relationships with overlaps
    synonyms: Mapped[List["SenseRelation"]] = relationship(
        foreign_keys="[SenseRelation.source_id]",
        primaryjoin="and_(Sense.id==SenseRelation.source_id, "
                   "SenseRelation.relation_type=='synonym')",
        back_populates="source",
        overlaps="antonyms,hypernyms,hyponyms,meronyms,holonyms"
    )
    antonyms: Mapped[List["SenseRelation"]] = relationship(
        foreign_keys="[SenseRelation.source_id]",
        primaryjoin="and_(Sense.id==SenseRelation.source_id, "
                   "SenseRelation.relation_type=='antonym')",
        back_populates="source",
        overlaps="synonyms,hypernyms,hyponyms,meronyms,holonyms"
    )
    hypernyms: Mapped[List["SenseRelation"]] = relationship(
        foreign_keys="[SenseRelation.source_id]",
        primaryjoin="and_(Sense.id==SenseRelation.source_id, "
                   "SenseRelation.relation_type=='hypernym')",
        back_populates="source",
        overlaps="synonyms,antonyms,hyponyms,meronyms,holonyms"
    )
    hyponyms: Mapped[List["SenseRelation"]] = relationship(
        foreign_keys="[SenseRelation.source_id]",
        primaryjoin="and_(Sense.id==SenseRelation.source_id, "
                   "SenseRelation.relation_type=='hyponym')",
        back_populates="source",
        overlaps="synonyms,antonyms,hypernyms,meronyms,holonyms"
    )
    meronyms: Mapped[List["SenseRelation"]] = relationship(
        foreign_keys="[SenseRelation.source_id]",
        primaryjoin="and_(Sense.id==SenseRelation.source_id, "
                   "SenseRelation.relation_type=='meronym')",
        back_populates="source",
        overlaps="synonyms,antonyms,hypernyms,hyponyms,holonyms"
    )
    holonyms: Mapped[List["SenseRelation"]] = relationship(
        foreign_keys="[SenseRelation.source_id]",
        primaryjoin="and_(Sense.id==SenseRelation.source_id, "
                   "SenseRelation.relation_type=='holonym')",
        back_populates="source",
        overlaps="synonyms,antonyms,hypernyms,hyponyms,meronyms"
    )


class SenseRelation(Base):
    """Model for semantic relationships between senses."""
    __tablename__ = "sense_relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    target_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    relation_type: Mapped[str] = mapped_column(String(50))  # synonym, antonym, etc.
    
    # Optional fields for additional context
    topics: Mapped[str | None] = mapped_column(String, nullable=True)
    taxonomic: Mapped[str | None] = mapped_column(String, nullable=True)
    roman: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Relationships
    source: Mapped[Sense] = relationship(
        foreign_keys=[source_id],
        back_populates="synonyms"
    )
    target: Mapped[Sense] = relationship(foreign_keys=[target_id])


class Gloss(Base):
    """Model for word definitions/glosses."""
    __tablename__ = "glosses"

    id: Mapped[int] = mapped_column(primary_key=True)
    sense_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    text: Mapped[str] = mapped_column(String)
    is_raw: Mapped[bool] = mapped_column(default=False)

    sense: Mapped[Sense] = relationship(back_populates="glosses")


class Example(Base):
    """Model for usage examples."""
    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(primary_key=True)
    sense_id: Mapped[int] = mapped_column(ForeignKey("senses.id"))
    text: Mapped[str | None] = mapped_column(String, nullable=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)
    english: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    roman: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    sense: Mapped[Sense] = relationship(back_populates="examples")
