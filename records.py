"""Cached LLM records: save / load / list / delete.

One JSON file per task under data_dir/<functions|variables|summaries|chunks>/,
keyed by (file, name, line) with a symbol fingerprint for cache invalidation.
"""
import hashlib
import json
import os

from util import sanitize_id

_SUBDIR = {'function': 'functions', 'variable': 'variables',
           'summary': 'summaries', 'chunk': 'chunks'}


def record_path(data_dir: str, relpath: str, kind: str, name: str,
                line: int) -> str:
    sub = _SUBDIR[kind]
    fhash = hashlib.md5(relpath.encode('utf-8')).hexdigest()[:10]
    fname = f'{kind}_{fhash}_{sanitize_id(name)}_{line}.json'
    return os.path.join(data_dir, sub, fname)


def save_record(data_dir: str, relpath: str, kind: str, name: str, line: int,
                prose: dict, fingerprint: str, symbol: dict):
    path = record_path(data_dir, relpath, kind, name, line)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {
        'schema': 'doc_maker/record@1',
        'kind': kind,
        'file': relpath,
        'name': name,
        'line': line,
        'symbol': symbol,
        'prose': prose,
        'fingerprint': fingerprint,
    }
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    return path


def load_record(data_dir: str, relpath: str, kind: str, name: str,
                line: int, fingerprint: str):
    path = record_path(data_dir, relpath, kind, name, line)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            rec = json.load(fh)
    except (ValueError, OSError):
        return None
    if rec.get('fingerprint') != fingerprint:
        return None
    return rec.get('prose')


def list_records(data_dir: str, kind: str):
    sub = _SUBDIR[kind]
    d = os.path.join(data_dir, sub)
    out = {}
    if not os.path.isdir(d):
        return out
    for fname in sorted(os.listdir(d)):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(d, fname), 'r', encoding='utf-8') as fh:
                rec = json.load(fh)
            out[(rec.get('file'), rec.get('name'), rec.get('line'))] = rec
        except (ValueError, OSError):
            continue
    return out


def delete_records_for(data_dir: str, relpaths) -> int:
    """Delete cached LLM records that belong to the given source files."""
    removed = 0
    for kind in _SUBDIR:
        for (file, name, line), _rec in list_records(data_dir, kind).items():
            if file in relpaths:
                try:
                    os.remove(record_path(data_dir, file, kind, name, line))
                    removed += 1
                except OSError:
                    pass
    return removed
