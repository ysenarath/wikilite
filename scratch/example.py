from typing import Dict

from wikilite.utils import wiktextract
from wikilite.utils.wiktextract import get_relations, singularize_relation

if __name__ == "__main__":
    # word -> definition -> [examples]
    data: Dict[str, Dict[str, list]] = {}
    triples = set()
    for entry in wiktextract.load():
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
            data[entry.word][definition].extend(sense.examples)
    # words in triples
    words = {w for w, _, _ in triples} | {w for _, _, w in triples}
    # words in data
    words = words.intersection(data.keys())
    # filter data
    data = [(w, d) for w, d in data.items() if w in words]
    # filter triples
    triples = {t for t in triples if t[0] in words or t[2] in words}
    print("Summary:")
    print(f"  {len(data)} words")
    print(f"  {len(triples)} triples")
    print("Memory usage (MB):")
    import sys

    print(f"  {sys.getsizeof(data) / 1024 / 1024:.2f} data")
    print(f"  {sys.getsizeof(triples) / 1024 / 1024:.2f} triples")
