"""Output management: purging the output/data dirs and the .doc_cache
(md5-per-file record that invalidates cached LLM records on changes)."""
import json
import os
import shutil

from kodama_docs.records import delete_records_for
from kodama_docs.scan import file_md5
from kodama_docs.util import log


def _dangerous_dirs() -> set:
    cwd = os.path.abspath(os.getcwd())
    root = os.path.splitdrive(cwd)[0] + os.sep
    return {cwd, os.path.abspath(os.path.expanduser('~')), root}


def _contains(parent: str, child: str) -> bool:
    """True when ``child`` is ``parent`` or lives under it (real paths)."""
    p = os.path.realpath(parent)
    c = os.path.realpath(child)
    try:
        return os.path.commonpath([p, c]) == p
    except ValueError:  # different drives on Windows
        return False


def _guard_delete(path: str, cfg: dict) -> str:
    d = os.path.abspath(path)
    if d in _dangerous_dirs():
        raise SystemExit(f'refusing to delete dangerous path: {d}')
    for key, label in (('source_dir', 'source directory'),
                       ('manual_doc', 'manual-doc source')):
        protected = cfg.get(key)
        if protected and _contains(d, protected):
            raise SystemExit(f'refusing to delete {d}: it contains the '
                             f'{label} {protected}')
    return d


def purge_outputs(cfg: dict) -> list:
    """Delete the output (docs + meta) and data directories. Returns the
    paths actually removed."""
    removed = []
    for d in (cfg['output_dir'], cfg['data_dir']):
        d = _guard_delete(d, cfg)
        if os.path.isdir(d):
            shutil.rmtree(d)
            removed.append(d)
            log(f'  purged {d}')
    return removed


def reset_output(cfg: dict) -> None:
    """Remove generated docs before a render, so deleted source files and
    disabled features cannot leave stale pages behind.

    ``.doc_cache`` is deliberately kept: it is what lets the next run
    detect changed/removed *sources* without a full analysis. Everything
    else in the output directory is generated and safe to recreate."""
    out = _guard_delete(cfg['output_dir'], cfg)
    data = cfg.get('data_dir')
    if data and _contains(out, data):
        raise SystemExit(f'refusing to reset {out}: it contains the data '
                         f'directory {data}')
    if not os.path.isdir(out):
        return
    for entry in os.listdir(out):
        if entry == '.doc_cache':
            continue
        path = os.path.join(out, entry)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            try:
                os.remove(path)
            except OSError:
                pass


def _doc_cache_path(cfg: dict) -> str:
    return os.path.join(cfg['output_dir'], '.doc_cache')


def load_doc_cache(cfg: dict):
    try:
        with open(_doc_cache_path(cfg), 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return {str(k): str(v) for k, v in (data.get('files') or {}).items()}
    except (ValueError, OSError):
        return None


def write_doc_cache(cfg: dict, files) -> None:
    md5s = {f['relpath']: file_md5(f['full']) for f in files}
    os.makedirs(cfg['output_dir'], exist_ok=True)
    with open(_doc_cache_path(cfg), 'w', encoding='utf-8') as fh:
        json.dump({'schema': 'kodama_docs/doc_cache@1', 'files': md5s},
                  fh, ensure_ascii=False, indent=1)
    log(f'doc cache: {len(md5s)} files -> {_doc_cache_path(cfg)}')


def check_doc_cache(cfg: dict, files) -> bool:
    """Compare the .doc_cache hashes (relpath -> md5) against the current
    files. For changed or removed files, delete their cached LLM records
    and force a fresh analysis. Returns True if anything was stale."""
    cache = load_doc_cache(cfg)
    if cache is None:
        return False
    cur = {f['relpath']: file_md5(f['full']) for f in files}
    dirty = sorted(r for r in cur if r in cache and cache[r] != cur[r])
    stale = sorted(r for r in cache if r not in cur)
    if not dirty and not stale:
        return False
    removed = delete_records_for(cfg['data_dir'], set(dirty) | set(stale))
    log(f'doc cache stale: {len(dirty)} changed, {len(stale)} removed, '
        f'{removed} cached record(s) deleted -> those files will be re-run')
    for r in (dirty + stale)[:8]:
        log(f'  stale: {r}')
    return True
