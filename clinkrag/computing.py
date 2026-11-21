"""Read-only proceedings snapshot. All search results point back to attributed abstracts."""
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
from threading import Lock

DATA = Path(__file__).with_name('data')/'computing.jsonl'
FEATURES = DATA.with_suffix('.index.gz')
_BUILD = Lock()


def feature_signature(corpus):
    # Bind bundled word counts to both the exact documents and the tokenizers.
    # Normalize source line endings so a Windows Git checkout uses the same file.
    digest = hashlib.sha256(corpus.encode('utf-8'))
    for name in ('library.py','technical.py','retrieval.py','paper_ids.py'):
        digest.update(b'\0')
        digest.update(Path(__file__).with_name(name).read_text(encoding='utf-8').encode('utf-8'))
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _collection():
    from .library import LibraryIndex

    corpus = DATA.read_text(encoding='utf-8')
    papers = [json.loads(line) for line in corpus.splitlines() if line.strip()]
    metadata = {p['paper_id']:{k:p[k] for k in ('container','volume','page','publication_type') if k in p}
                for p in papers}
    try:
        with gzip.open(FEATURES,'rt',encoding='utf-8') as stream:
            snapshot = json.load(stream)
        if snapshot['signature'] == feature_signature(corpus):
            return LibraryIndex(papers,features=snapshot['features']), metadata
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        pass  # A source checkout with no matching cache can always build from the abstracts.
    return LibraryIndex(papers), metadata


def search_computing(question, limit=5):
    # Serialize the first build only. Multiple HTTP workers can score concurrently.
    with _BUILD:
        index, records = _collection()
    result = index.search(question, limit=limit)
    for item in result['items']:
        item.update(records[item['paper_id']])
    return result
