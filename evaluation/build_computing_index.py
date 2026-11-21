"""Prepare portable term counts for the licensed computing collection, using no network."""
import gzip
import json

from clinkrag.computing import DATA, FEATURES, feature_signature
from clinkrag.library import library_features


def main():
    corpus = DATA.read_text(encoding='utf-8')
    papers = [json.loads(line) for line in corpus.splitlines() if line.strip()]
    snapshot = {'signature':feature_signature(corpus), 'features':library_features(papers)}
    compressed = gzip.compress(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')).encode('utf-8'),
                               compresslevel=9,mtime=0)
    temp = FEATURES.with_suffix('.tmp')
    temp.write_bytes(compressed)
    temp.replace(FEATURES)
    print(f'{len(papers)} records, {len(compressed):,} compressed bytes')


if __name__=='__main__':
    main()
