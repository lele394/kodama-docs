"""SCAN + PARSE/EXTRACT phase: walk the source tree, extract symbols with
the language backends, cache the analysis (symbols.json), report."""
import hashlib
import json
import os

import backends
import graph as gmod
from records import load_record
from util import log
from rich.text import Text as RText
from rich.table import Table as RTable
from rich.console import Console as RConsole
from rich import box


def scan_files(cfg: dict):
    """Walk the source tree. Returns (files, skipped): the accepted file
    dicts, plus {reason: [relpath, ...]} for files not accepted (excluded
    by config, unsupported extension, or too large)."""
    excl = set(cfg['exclude'])
    exts = set(backends.EXTRACTORS)
    out = []
    skipped = {'exclude': [], 'unsupported': [], 'oversize': []}
    for dirpath, dirnames, filenames in os.walk(cfg['source_dir']):
        dirnames.sort()
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, cfg['source_dir']).replace('\\', '/')
            if any(part in excl for part in rel.split('/')):
                skipped['exclude'].append(rel)
                continue
            if os.path.splitext(fn)[1].lower() not in exts:
                skipped['unsupported'].append(rel)
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > cfg['max_file_bytes']:
                skipped['oversize'].append(rel)
                continue
            out.append({'full': full, 'relpath': rel, 'size': size})
    return out, skipped


def file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def scan_fingerprint(files) -> str:
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x['relpath']):
        h.update(f['relpath'].encode('utf-8'))
        h.update(file_md5(f['full']).encode('ascii'))
    return h.hexdigest()


# ------------------------------------------------------------- analysis

def analyze_files(cfg: dict, files):
    results, ok, bad, binary = [], 0, 0, 0
    for i, f in enumerate(files, 1):
        try:
            with open(f['full'], 'rb') as fh:
                head = fh.read(65536)
            if b'\x00' in head:
                binary += 1
                continue
            src = open(f['full'], 'r', encoding='utf-8', errors='replace').read()
            r = backends.extract(src, f['relpath'])
        except Exception as e:  # noqa: BLE001 - per-file isolation by design
            bad += 1
            if bad <= 10:
                log(f'  analyze failed {f["relpath"]}: {e}')
            continue
        r['relpath'] = f['relpath']
        r['lines'] = len(src.splitlines())
        r['size'] = f['size']
        results.append(r)
        if i % 200 == 0:
            log(f'  analyzed {i}/{len(files)}')
    return results, len(results), bad, binary


def save_symbols(cfg: dict, files, fingerprint: str):
    path = os.path.join(cfg['data_dir'], 'symbols.json')
    os.makedirs(cfg['data_dir'], exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({'schema': 'doc_maker/symbols@1', 'fingerprint': fingerprint,
                   'file_count': len(files), 'files': files},
                  fh, ensure_ascii=False)
    log(f'  saved {path} ({os.path.getsize(path) // 1024} KiB)')


def load_symbols(cfg: dict):
    path = os.path.join(cfg['data_dir'], 'symbols.json')
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data['files'], data['fingerprint']
    except (ValueError, KeyError, OSError):
        return None, None


# --------------------------------------------------------- scan report

def report_scan(cfg: dict, analysis, skipped):
    """Post-analysis summary table: accepted files per extension, files
    already fully documented (record cache), and files skipped by the
    config."""
    doccfg = cfg['documentation']
    inc_anon = bool(doccfg.get('include_anonymous_functions', False))
    want_fn = bool(doccfg.get('generate_function_docs'))
    want_var = bool(doccfg.get('generate_variable_docs'))
    want_sum = bool(doccfg.get('generate_file_summaries'))
    dd = cfg['data_dir']

    exts = {}
    c_files = c_fn = c_var = 0
    for f in analysis:
        rel = f['relpath']
        ext = os.path.splitext(rel)[1].lower().lstrip('.') or '?'
        fns = [fn for fn in (f.get('functions') or [])
               if inc_anon or fn['name'] != 'anon']
        nvar = len(f.get('file_vars') or [])
        s = exts.setdefault(ext, [0, 0, 0])
        s[0] += 1
        s[1] += len(fns) if want_fn else 0
        s[2] += nvar if want_var else 0
        # record cache: is this file already fully documented?
        fp = gmod.fingerprint([f])
        tasks = ok = 0
        for fn in fns:
            if want_fn:
                tasks += 1
                if load_record(dd, rel, 'function', fn['name'],
                               fn['line'], fp):
                    ok += 1
        for v in f.get('file_vars') or []:
            if want_var:
                tasks += 1
                if load_record(dd, rel, 'variable', v['name'],
                               v['line'], fp):
                    ok += 1
        if want_sum:
            tasks += 1
            if load_record(dd, rel, 'summary', 'file', 1, fp):
                ok += 1
        if tasks and ok == tasks:
            c_files += 1
            c_fn += len(fns)
            c_var += nvar

    t = RTable(box=box.SIMPLE, pad_edge=False, padding=(0, 2),
               header_style='bold')
    t.add_column('extension')
    for col in ('files', 'functions', 'vars', 'total tasks'):
        t.add_column(col, justify='right')
    for ext in sorted(exts, key=lambda e: (-exts[e][0], e)):
        nf, fn_, nv = exts[ext]
        tasks = fn_ + nv + (nf if want_sum else 0)
        t.add_row(RText(f'.{ext}', style='bold green'),
                  RText(str(nf), style='green'),
                  RText(str(fn_), style='green'),
                  RText(str(nv), style='green'),
                  RText(str(tasks), style='bold green'))
    c_tasks = c_fn + c_var + (c_files if want_sum else 0)
    t.add_row(RText('Skipped (cached)', style='bold orange3'),
              RText(str(c_files), style='orange3'),
              RText(str(c_fn), style='orange3'),
              RText(str(c_var), style='orange3'),
              RText(str(c_tasks), style='bold orange3'))
    skip_n = sum(len(v) for v in skipped.values())
    t.add_row(RText('Skipped (exclude)', style='bold red'),
              RText(str(skip_n), style='red'),
              RText('—', style='red'),
              RText('—', style='red'),
              RText('—', style='red'))
    RConsole().print(t)
    for reason, rels in sorted(skipped.items()):
        if rels:
            shown = ', '.join(rels[:5]) + (f' (+{len(rels) - 5} more)'
                                           if len(rels) > 5 else '')
            log(f'  skipped {reason}: {len(rels)} — {shown}')
