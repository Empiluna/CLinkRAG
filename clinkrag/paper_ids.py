"""Resolve explicitly named publications without treating ordinary numbers as arXiv IDs."""
import re
import unicodedata

_ARXIV_NUMBER = r'(?:\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}|[a-z][a-z.\-]+/\d{7})(?:v\d+)?'
_PREFIX = r'(?:arxiv\s*[:：]?\s*|(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf|html)/)'
_ARXIV = rf'(?P<arxiv>{_ARXIV_NUMBER})(?:\.pdf)?(?![a-z0-9]|\.\d)'
_DOI = (r'(?<![a-z0-9])(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?'
        r'(?P<doi>10\.\d{4,9}/(?:(?!;10\.\d{4,9}/)[-._;+()/:a-z0-9])+)')
_REFERENCE = re.compile(_DOI+'|'+_PREFIX+_ARXIV, re.I | re.ASCII)
_LOCAL_REFERENCE = re.compile(_DOI+'|'+r'(?<![.a-z0-9])'+_PREFIX+'?'+_ARXIV,
                              re.I | re.ASCII)


def _arxiv(identifier):
    return 'ARXIV:' + re.sub(r'v\d+$', '', identifier, flags=re.I).lower()


def _doi(identifier):
    suffix = identifier.rstrip('.,;:')
    while suffix.endswith(')') and suffix.count(')') > suffix.count('('):
        suffix = suffix[:-1].rstrip('.,;:')
    archive = re.fullmatch(rf'10\.48550/arxiv\.({_ARXIV_NUMBER})', suffix, re.I | re.ASCII)
    return _arxiv(archive.group(1)) if archive else 'DOI:' + suffix.lower()


def paper_references(text, *, allow_bare_arxiv=False):
    """Canonical IDs in reading order. A bare arXiv number is accepted on its own."""
    text = unicodedata.normalize('NFKC', str(text or '')).strip()
    if re.fullmatch(_ARXIV_NUMBER, text, re.I | re.ASCII):
        return [_arxiv(text)]
    pattern=_LOCAL_REFERENCE if allow_bare_arxiv else _REFERENCE
    return list(dict.fromkeys(_arxiv(m['arxiv']) if m['arxiv'] else _doi(m['doi'])
                              for m in pattern.finditer(text)))


def without_references(text, *, allow_bare_arxiv=False):
    pattern=_LOCAL_REFERENCE if allow_bare_arxiv else _REFERENCE
    text=unicodedata.normalize('NFKC', str(text or ''))
    if re.fullmatch(_ARXIV_NUMBER,text.strip(),re.I | re.ASCII):
        return ''
    return pattern.sub(' ',text)


def matches_reference(reference, paper):
    fields = paper.get('externalIds') or {}
    if not isinstance(fields, dict):
        return False
    doi, arxiv = fields.get('DOI'), fields.get('ArXiv')
    return ((isinstance(doi, str) and _doi(doi) == reference) or
            (isinstance(arxiv, str) and _arxiv(arxiv) == reference))
