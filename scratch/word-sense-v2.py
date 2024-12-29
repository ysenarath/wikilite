import pandas as pd

from wikilite.utils import wiktextract

if __name__ == "__main__":
    words = []
    forms = {}
    for page in wiktextract.load():
        forms[page.word] = forms.get(page.word, [page.word]) + [
            f["form"] for f in page.forms
        ]
        word = page.word
        if len(page.senses) == 0:
            words.append((word, word))
        else:
            for sense in page.senses:
                sense_glosses = sense.raw_glosses
                if len(sense_glosses) == 0 and sense.glosses:
                    sense_glosses = sense.glosses
                words.append((word, " ".join(sense_glosses)))
    forms_df = pd.DataFrame(forms.items(), columns=["word", "forms"])
    forms_df = forms_df.explode("forms")
    words_df = pd.DataFrame(words, columns=["word", "definition"])
    words_df["text"] = (words_df["word"] + ". " + words_df["definition"]).str.strip()
    words_df = (
        words_df.reset_index(drop=True).drop(columns="id").reset_index(names="id")
    )


if __name__ == "__main__":
    rel_senses = []
    for word in wiktextract.load():
        all_relations = []
        for s in wiktextract.get_relations(word).values():
            all_relations.extend(s)
        for sense in word.senses:
            for s in wiktextract.get_relations(sense).values():
                all_relations.extend(s)
        for rel in all_relations:
            if rel.sense:
                rel_senses.append((rel.word, rel.sense))
    rel_senses_df = pd.DataFrame(rel_senses, columns=["word", "sense"])
    rel_senses_df = rel_senses_df.reset_index(drop=True).reset_index(names="id")
    rel_senses_df["text"] = (
        rel_senses_df["word"] + ". " + rel_senses_df["sense"]
    ).str.strip()
