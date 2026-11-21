"""Make the bundled Chinese query glossary from an official CC-CEDICT gzip download."""
import argparse
from collections import defaultdict
import gzip
import hashlib
from html.parser import HTMLParser
import re
from pathlib import Path
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'clinkrag/data/cedict-glosses.idx'
ENTRY = re.compile(r'^(\S+) (\S+) \[.*?\] /(.*)/$')
HAN = re.compile(r'[\u3400-\u9fff]{2,12}')
ANNOTATION = re.compile(r'\([^()]*\)')
WORDS = re.compile(r"[a-z]+(?:[ -][a-z]+){0,3}")
SKIP = re.compile(r'\b(?:classifier|surname|variant of|also written|abbr\. for|slang|idiom|'
                  r'archaic|dialect|onomatopoeia|place name|see also|literary|euphemism)\b', re.I)
COMPUTING = re.compile(r'\((?:computing|computer(?: science)?|math(?:ematics)?\.?|electronics|'
                       r'statistics|physics|engineering|programming|internet|telecom(?:munications)?)\)', re.I)


def build(archive, output):
    rows = defaultdict(list)
    for line in gzip.decompress(archive.read_bytes()).decode('utf-8-sig').splitlines():
        match = ENTRY.match(line)
        if not match:
            continue
        traditional, simple, definition = match.groups()
        senses = []
        for part in definition.split('/'):
            if SKIP.search(part):
                continue
            field = bool(COMPUTING.search(part))
            for gloss in ANNOTATION.sub(' ', part).split(';'):
                gloss = ' '.join(gloss.split()).strip().removeprefix('to ').removeprefix('a ').removeprefix('an ')
                if WORDS.fullmatch(gloss):
                    senses.append((field, gloss))
        # Give an explicitly technical sense precedence over a colloquial homonym.
        senses.sort(key=lambda sense: not sense[0])
        for form in dict.fromkeys([simple, traditional]):
            if HAN.fullmatch(form):
                rows[form].extend(word for _,word in senses)
    blocks = defaultdict(list)
    for key in sorted(rows):
        if rows[key]:
            blocks[ord(key[0]) >> 7].append(key+'\t'+'|'.join(dict.fromkeys(rows[key]))+'\n')
    with ZipFile(output,'w') as index:
        for page,lines in sorted(blocks.items()):
            info = ZipInfo(str(page),date_time=(2026,1,1,0,0,0))
            index.writestr(info,''.join(lines).encode(),compress_type=ZIP_DEFLATED,compresslevel=9)
    print('Source SHA-256',hashlib.sha256(archive.read_bytes()).hexdigest())
    print('Compiled headword forms', sum(map(len,blocks.values())), 'bytes', output.stat().st_size)


class Headings(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.headings = {}
        self.current = None
        self.feed(path.read_text(encoding='utf-8'))

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        key = attrs.get('id','')
        if tag=='h2' and attrs.get('class')=='hide-from-toc':
            self.headings[key] = attrs.get('data-text','')
        if tag=='dt' and key.startswith('term-'):
            self.current = key
            self.headings[key] = ''

    def handle_endtag(self, tag):
        if tag=='dt':
            self.current = None

    def handle_data(self, value):
        if self.current and value != '¶':
            self.headings[self.current] += value


def build_terms(directory):
    google_en = Headings(directory / 'google-ml-en.html').headings
    google_zh = Headings(directory / 'google-ml-zh.html').headings
    python = Headings(directory / 'python-zh.html').headings
    paired = [(google_en[k],zh) for k,zh in google_zh.items() if k in google_en]
    paired.extend(s.split(' -- ',1) for s in python.values() if ' -- ' in s)
    names = defaultdict(list)
    for en,zh in paired:
        key = ANNOTATION.sub('',unicodedata.normalize('NFKC',zh)).strip()
        value = ANNOTATION.sub('',en.lstrip()).strip().lower()
        if HAN.fullmatch(key) and WORDS.fullmatch(value):
            names[key].append(value)
    path = ROOT/'clinkrag/data/technical-names.tsv'
    path.write_text(''.join(k+'\t'+'|'.join(dict.fromkeys(names[k]))+'\n' for k in sorted(names)),
                    encoding='utf-8', newline='\n')
    print('Subject headwords',len(names))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=Path,help='Official cedict_1_0_ts_utf-8_mdbg.txt.gz')
    ap.add_argument('--output',type=Path,default=TARGET)
    ap.add_argument('--terminology-dir',type=Path,help='Local Google ML (zh/en) and Python (zh) HTML snapshots')
    args=ap.parse_args()
    build(args.archive,args.output)
    if args.terminology_dir:
        build_terms(args.terminology_dir)
