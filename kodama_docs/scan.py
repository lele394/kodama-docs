"""SCAN + PARSE/EXTRACT phase: walk the source tree, extract symbols with
the language backends, cache the analysis (symbols.json), report."""
import hashlib
import json
import os

import backends
import kodama_docs.graph as gmod
from kodama_docs.records import load_record
from kodama_docs.tasks import (function_fp, settings_fp, summary_fp,
                               variable_fp)
from kodama_docs.util import log
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
    """Analyze the accepted files. Returns ``(results, status_map)``:

    - ``results`` — the extracted symbol dicts (each with ``relpath``,
      ``lines``, ``size`` and ``status: 'ok'``);
    - ``status_map`` — ``{relpath: {'status': 'ok'|'failed'|'binary',
      'error'?: str}}`` for every accepted file (P0-3: analysis failures
      are tracked per file and surfaced in the report and in
      diagnostics.json, never dropped)."""
    results, status_map = [], {}
    bad = 0
    for i, f in enumerate(files, 1):
        rel = f['relpath']
        try:
            with open(f['full'], 'rb') as fh:
                head = fh.read(65536)
            if b'\x00' in head:
                status_map[rel] = {'status': 'binary'}
                continue
            src = open(f['full'], 'r', encoding='utf-8', errors='replace').read()
            r = backends.extract(src, rel)
        except Exception as e:  # noqa: BLE001 - per-file isolation by design
            bad += 1
            status_map[rel] = {'status': 'failed',
                               'error': f'{type(e).__name__}: {e}'}
            if bad <= 10:
                log(f'  analyze failed {rel}: {e}')
            continue
        r['relpath'] = rel
        r['lines'] = len(src.splitlines())
        r['size'] = f['size']
        r['status'] = 'ok'
        results.append(r)
        status_map[rel] = {'status': 'ok'}
        if i % 200 == 0:
            log(f'  analyzed {i}/{len(files)}')
    return results, status_map


def save_diagnostics(data_dir, fp, astatus, diag):
    """Write ``diagnostics.json``: per-file analysis status plus the graph
    resolution diagnostics (ambiguous call sites, external references,
    unresolved imports, inferred calls). Failures and unresolved symbols
    must stay visible to the user (P0-3), so this is always written."""
    counts = {'ok': 0, 'failed': 0, 'binary': 0}
    for st in astatus.values():
        st = st.get('status', 'ok')
        counts[st] = counts.get(st, 0) + 1
    graph = diag or {}
    out = {
        'schema': 'kodama_docs/diagnostics@1',
        'fingerprint': fp,
        'analysis': {'counts': counts, 'files': astatus},
        'graph': {
            'ambiguous_calls': sorted(
                graph.get('ambiguous_calls', []),
                key=lambda d: (d.get('file', ''), d.get('line') or 0)),
            'external_calls': sorted(
                graph.get('external_calls', []),
                key=lambda d: (d.get('file', ''), d.get('line') or 0,
                               d.get('name') or '')),
            'builtin_calls': sorted(
                graph.get('builtin_calls', []),
                key=lambda d: (d.get('file', ''), d.get('line') or 0,
                               d.get('name') or '')),
            'unresolved_imports': sorted(
                graph.get('unresolved_imports', []),
                key=lambda d: (d.get('file', ''), d.get('line') or 0,
                               d.get('module') or '')),
            'inferred_calls': sorted(
                graph.get('inferred_calls', []),
                key=lambda d: (d.get('file', ''), d.get('line') or 0,
                               d.get('name') or '')),
        },
    }
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, 'diagnostics.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    g = out['graph']
    log(f'  saved {path} '
        f'(ambiguous={len(g["ambiguous_calls"])}, '
        f'external={len(g["external_calls"])}, '
        f'builtin={len(g["builtin_calls"])}, '
        f'unresolved_imports={len(g["unresolved_imports"])}, '
        f'inferred={len(g["inferred_calls"])})')


def save_symbols(cfg: dict, files, fingerprint: str):
    path = os.path.join(cfg['data_dir'], 'symbols.json')
    os.makedirs(cfg['data_dir'], exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({'schema': 'kodama_docs/symbols@1', 'fingerprint': fingerprint,
                   'file_count': len(files),
                   'backends': backends.active_backend_ids(),
                   'files': files},
                  fh, ensure_ascii=False)
    log(f'  saved {path} ({os.path.getsize(path) // 1024} KiB)')


def load_symbols(cfg: dict):
    """(files, fingerprint, backends_stamp) from symbols.json, or
    (None, None, None) when absent/corrupt. The stamp records which
    backend name@version extracted each extension (see
    backends.active_backend_ids)."""
    path = os.path.join(cfg['data_dir'], 'symbols.json')
    if not os.path.exists(path):
        return None, None, None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data['files'], data['fingerprint'], data.get('backends')
    except (ValueError, KeyError, OSError):
        return None, None, None


# --------------------------------------------------------- scan report

def report_scan(cfg: dict, analysis, skipped, g, diag, astatus):
    """Post-analysis summary: accepted files per extension, files already
    fully documented (record cache), files skipped by the config — and the
    per-file analysis status plus the graph resolution diagnostics
    (P0-3: failures and unresolved references are always shown).

    The "Skipped (cached)" count uses the same per-task fingerprints as the
    LLM phase (kodama_docs.tasks), so it never counts a stale record as
    valid."""
    doccfg = cfg['documentation']
    inc_anon = bool(doccfg.get('include_anonymous_functions', False))
    want_fn = bool(doccfg.get('generate_function_docs'))
    want_var = bool(doccfg.get('generate_variable_docs'))
    want_sum = bool(doccfg.get('generate_file_summaries'))
    dd = cfg['data_dir']
    sfn = settings_fp(cfg, 'function') if want_fn else None
    svar = settings_fp(cfg, 'variable') if want_var else None
    ssum = settings_fp(cfg, 'summary') if want_sum else None

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
        # record cache: is this file already fully documented? Each task
        # kind has its own fingerprint (tasks.py, shared with llm_phase).
        tasks = ok = 0
        for fn in fns:
            if want_fn:
                tasks += 1
                nid = gmod.node_id_fn(rel, fn['name'], fn['line'])
                ins, outs = gmod.graph_neighbor_names(g, nid)
                if load_record(dd, rel, 'function', fn['name'],
                               fn['line'], function_fp(rel, fn, ins, outs, sfn)):
                    ok += 1
        for v in f.get('file_vars') or []:
            if want_var:
                tasks += 1
                if load_record(dd, rel, 'variable', v['name'],
                               v['line'], variable_fp(rel, v, svar)):
                    ok += 1
        if want_sum:
            tasks += 1
            if load_record(dd, rel, 'summary', 'file', 1,
                           summary_fp(rel, f, ssum)):
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

    # ---- analysis status (per-file) — failures are always shown ---------
    counts = {'ok': 0, 'failed': 0, 'binary': 0}
    for st in astatus.values():
        k = st.get('status', 'ok')
        counts[k] = counts.get(k, 0) + 1
    log(f'  analysis: {counts["ok"]} ok, {counts["failed"]} failed, '
        f'{counts["binary"]} binary (of {len(astatus)} files)')
    for rel in sorted(k for k, v in astatus.items()
                      if v.get('status') == 'failed'):
        log(f'  ! failed to analyze {rel}: '
            f'{astatus[rel].get("error", "")}')
    if counts['binary']:
        log(f'  note: {counts["binary"]} file(s) detected as binary '
            f'(no symbols extracted)')

    # ---- graph resolution diagnostics (per P0-2: visible, not guessed) --
    graph = diag or {}
    amb = graph.get('ambiguous_calls', [])
    extc = graph.get('external_calls', [])
    unc = graph.get('unresolved_imports', [])
    inf = graph.get('inferred_calls', [])
    log(f'  resolution: {len(amb)} ambiguous call site(s) '
        f'(no edge written), {len(extc)} external reference(s), '
        f'{len(unc)} unresolved import(s), {len(inf)} inferred call(s)')
    for d in amb[:10]:
        log(f'  ! ambiguous {d.get("name")} at {d.get("file")}:{d.get("line")}: '
            f'candidates: {", ".join(d.get("candidates") or [])}')
    if len(amb) > 10:
        log(f'  ... and {len(amb) - 10} more (see diagnostics.json)')
    for d in unc[:10]:
        log(f'  ! unresolved import {d.get("module")} at '
            f'{d.get("file")}:{d.get("line")}')
    if len(unc) > 10:
        log(f'  ... and {len(unc) - 10} more (see diagnostics.json)')
