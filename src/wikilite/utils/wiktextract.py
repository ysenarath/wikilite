from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import tqdm
import wikilite
import subprocess
from pydantic import BaseModel, Field


class WordLinkage(BaseModel):
    word: str
    sense: Optional[str] = None
    topics: Optional[List[str]] = None
    taxonomic: Optional[str] = None
    tags: Optional[List[str]] = None
    roman: Optional[str] = None
    english: Optional[str] = None
    alt: Optional[str] = None


class WordReference(BaseModel):
    word: str
    extra: Optional[str] = None


class Example(BaseModel):
    text: Optional[str] = None
    ref: Optional[str] = None
    english: Optional[str] = None
    type: Optional[str] = None
    roman: Optional[str] = None
    note: Optional[str] = None


class WordSense(BaseModel):
    glosses: List[str] = Field(default_factory=list)
    raw_glosses: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    categories: List[Dict[str, Any]] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    alt_of: List[WordReference] = Field(default_factory=list)
    form_of: List[WordReference] = Field(default_factory=list)
    translations: List[Dict[str, Any]] = Field(default_factory=list)
    synonyms: List[WordLinkage] = Field(default_factory=list)
    antonyms: List[WordLinkage] = Field(default_factory=list)
    hypernyms: List[WordLinkage] = Field(default_factory=list)
    holonyms: List[WordLinkage] = Field(default_factory=list)
    meronyms: List[WordLinkage] = Field(default_factory=list)
    coordinate_terms: List[WordLinkage] = Field(default_factory=list)
    derived: List[WordLinkage] = Field(default_factory=list)
    related: List[WordLinkage] = Field(default_factory=list)
    senseid: List[str] = Field(default_factory=list)
    wikipedia: List[str] = Field(default_factory=list)
    examples: List[Example] = Field(default_factory=list)
    english: Optional[str] = None

    @property
    def definitions(self) -> List[str]:
        if self.glosses:
            return self.glosses
        if self.raw_glosses:
            return self.raw_glosses
        raise ValueError(f"no definition found for {self}")


class WordEntry(BaseModel):
    word: str
    pos: str
    lang: str
    lang_code: str
    senses: List[WordSense]
    forms: List[
        Dict[
            str, Any
        ]  # {form: str, tags: List[str], ipa: str, roman: str, source: str}
    ] = Field(default_factory=list)
    sounds: List[Dict[str, Any]] = Field(default_factory=list)
    categories: List[Dict[str, Any]] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    translations: List[Dict[str, Any]] = Field(default_factory=list)
    etymology_text: Optional[str] = None
    etymology_templates: Optional[List[Dict[str, Any]]] = None
    etymology_number: int = 0
    descendants: List[Dict[str, Any]] = Field(default_factory=list)
    synonyms: List[WordLinkage] = Field(default_factory=list)
    antonyms: List[WordLinkage] = Field(default_factory=list)
    hypernyms: List[WordLinkage] = Field(default_factory=list)
    holonyms: List[WordLinkage] = Field(default_factory=list)
    meronyms: List[WordLinkage] = Field(default_factory=list)
    derived: List[WordLinkage] = Field(default_factory=list)
    related: List[WordLinkage] = Field(default_factory=list)
    coordinate_terms: List[WordLinkage] = Field(default_factory=list)
    wikidata: Optional[List[str]] = None
    wiktionary: Optional[str] = None
    head_templates: List[Dict[str, Any]] = Field(default_factory=list)
    inflection_templates: List[Dict[str, Any]] = Field(default_factory=list)


def load(path: Path | str | None = None) -> Generator[WordEntry, None, None]:
    if path is None:
        path = Path(wikilite.__file__).parents[2] / "resources" / "wiktextract-en.jsonl"
    nrows = int(subprocess.check_output(["wc", "-l", path], text=True).split()[0])
    with open(path, "r", encoding="utf-8") as f:
        for line in tqdm.tqdm(f, total=nrows):
            yield WordEntry.model_validate_json(line)


if __name__ == "__main__":
    definitions = {}
    def_group_id = 0
    definition_groups = {}
    for entry in load():
        for sense in entry.senses:
            sense_id = (entry.word, entry.pos, entry.lang_code, entry.etymology_number)
            try:
                definition_groups[def_group_id] = sense.definitions
                definitions.setdefault(sense_id, []).append(def_group_id)
                def_group_id += 1
            except ValueError:
                pass
    for group_id, definitions in definition_groups.items():
        if len(definitions) > 1:
            print(f"{group_id}: {definitions}")
    # for word, definitions in words.items():
    #     if len(definitions) == 0:
    #         print(word)
