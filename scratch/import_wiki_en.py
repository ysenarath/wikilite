from pathlib import Path
from wikilite.models import WikiLite

resources_path = Path(__file__).parent.parent / "resources"

wl = WikiLite.from_jsonl(resources_path / "wiktextract-en.jsonl", "wiktextract-en-v1")

print(wl.engine)
