from collections import defaultdict

from wikilite.utils import wiktextract
from wikilite.utils.wiktextract import get_relations, singularize_relation

if __name__ == "__main__":
    # word -> definition -> [examples]
    words = defaultdict(int)
    senses = {}
    word_and_senses = defaultdict(int)
    definition_index = {}
    for word in wiktextract.load():
        word_and_senses[word.word] += 1
        word_id = (word.word, word.pos, word.lang)
        for sense in word.senses:
            raw_glosses = sense.raw_glosses
            cleaned_glosses = sense.glosses
            if cleaned_glosses:
                assert len(raw_glosses), cleaned_glosses


def __():
    sense_id = (*word_id, definition)
    if sense_id in senses:
        # definition already seen (somehow!)
        continue
    words[word_id] += 1
    senses[sense_id] = words[word_id]
    word_and_senses[(word.word, definition)] += 1
    definition_index[definition]


def get_relations_alt(obj: wiktextract.WordSense | wiktextract.WordEntry) -> dict:
    print(f"Number of unique senses: {len(senses)}")
    relations = {}
    for word in wiktextract.load():
        word_id = (word.word, word.pos, word.lang)
        if word_id not in relations:
            relations[word_id] = {}
        for rel, links in get_relations(word).items():
            if rel not in relations[word_id]:
                relations[word_id][rel] = []
            for link in links:
                # relations[word_id][rel].append(link)
                if link.sense:
                    assert (link.word, link.sense) in word_and_senses, (
                        link.word,
                        link.sense,
                    )
                else:
                    assert link.word in word_and_senses, link.word
        for sense in word.senses:
            try:
                definition = sense.definition
            except ValueError:
                continue
            sense_id = (*word_id, definition)
            if sense_id in senses:
                # definition already seen (somehow!)
                continue
            words[word_id] += 1
            senses[sense_id] = words[word_id]
            if sense_id not in relations:
                relations[sense_id] = {}
            for rel, links in get_relations(word).items():
                if rel not in relations[word_id]:
                    relations[sense_id][rel] = []
                for link in links:
                    # relations[sense_id][rel].append(link)
                    if link.sense:
                        assert (link.word, link.sense) in word_and_senses, (
                            link.word,
                            link.sense,
                        )
                    else:
                        assert link.word in word_and_senses, link.word
