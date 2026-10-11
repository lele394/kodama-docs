"""doc_maker — deterministic Lua documentation generator.

Pipeline: SCAN -> PARSE/EXTRACT -> GRAPH -> (LLM PROSE) -> MARKDOWN.
Everything except the LLM prose strings is plain Python.
"""
import argparse
import hashlib
import json
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import ruamel.yaml
from rich.text import Text as RText
from rich.table import Table as RTable
from rich.console import Console as RConsole
from rich import box

from util import fence_lang, log, read_env_file, set_log_sink
import backends
import graph as gmod
import documentation as doc
from tui import TUI


# ------------------------------------------------------------------ config

def load_config(path: str) -> dict:
    yaml = ruamel.yaml.YAML()
    with open(path, 'r', encoding='utf-8') as fh:
        raw = yaml.load(fh)
    base = os.path.dirname(os.path.abspath(path))

    def rp(p):
        p = str(p)
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    llm = dict(raw.get('llm') or {})
    # api_key / base_url: the literal value "env" (or a missing value, the
    # default) means "read it from a .env file" instead of the config.
    envfile = {}
    for cand in (os.path.join(base, '.env'),
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')):
        if os.path.isfile(cand):
            envfile = read_env_file(cand)
            break
    for key in ('api_key', 'base_url'):
        val = llm.get(key)
        if val is None or str(val).strip().lower() == 'env':
            val = envfile.get(key)
            if not val:
                raise SystemExit(f'settings: llm.{key} is "env" but {key}'
                                 f' was not found in .env (looked in: {base},'
                                 f' {os.path.dirname(os.path.abspath(__file__))})')
            llm[key] = val

    return {
        'source_dir': rp(raw['project']['source_dir']),
        'output_dir': rp(raw['project']['output_dir']),
        'data_dir': rp(raw['project']['data_dir']),
        'exclude': [str(x) for x in (raw['project'].get('exclude') or [])],
        'max_file_bytes': int(raw['project'].get('max_file_bytes', 26214400)),
        'llm': llm,
        'context': dict(raw.get('context') or {}),
        'documentation': dict(raw.get('documentation') or {}),
        'copy_meta': bool(raw['project'].get('copy_meta', False)),
        'concurrency': int(raw.get('concurrency') or 2),
        'tui': dict(raw.get('tui') or {}),
        'prompts': {k: rp(v) for k, v in (raw.get('prompts') or {}).items()},
    }


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
                if doc.load_record(dd, rel, 'function', fn['name'],
                                   fn['line'], fp):
                    ok += 1
        for v in f.get('file_vars') or []:
            if want_var:
                tasks += 1
                if doc.load_record(dd, rel, 'variable', v['name'],
                                   v['line'], fp):
                    ok += 1
        if want_sum:
            tasks += 1
            if doc.load_record(dd, rel, 'summary', 'file', 1, fp):
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


# ------------------------------------------------- purge / doc cache

def _dangerous_dirs() -> set:
    cwd = os.path.abspath(os.getcwd())
    root = os.path.splitdrive(cwd)[0] + os.sep
    return {cwd, os.path.abspath(os.path.expanduser('~')), root}


def purge_outputs(cfg: dict) -> list:
    """Delete the output (docs + meta) and data directories. Returns the
    paths actually removed."""
    removed = []
    for d in (cfg['output_dir'], cfg['data_dir']):
        d = os.path.abspath(d)
        if d in _dangerous_dirs():
            raise SystemExit(f'refusing to delete dangerous path: {d}')
        if os.path.isdir(d):
            shutil.rmtree(d)
            removed.append(d)
            log(f'  purged {d}')
    return removed


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
        json.dump({'schema': 'doc_maker/doc_cache@1', 'files': md5s},
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
    removed = doc.delete_records_for(cfg['data_dir'], set(dirty) | set(stale))
    log(f'doc cache stale: {len(dirty)} changed, {len(stale)} removed, '
        f'{removed} cached record(s) deleted -> those files will be re-run')
    for r in (dirty + stale)[:8]:
        log(f'  stale: {r}')
    return True


# ---------------------------------------------------------------- LLM phase

def fn_length(fn: dict) -> int:
    return (fn.get('end_line') or fn['line']) - fn['line'] + 1


def chunk_notes(client, cfg, f, fn, prompts, retry, skip,
                maxchunk, chunktok, cpt=4, stage_cb=None):
    """Summarize a long function body part by part (each part cached
    separately) and return the body_note text for the merge prompt."""
    chunks = doc.fn_chunks(fn.get('body') or '', maxchunk, chunktok, cpt)
    if not chunks:
        return 'Source: (empty body)'
    notes = []
    for ci, ct in enumerate(chunks, 1):
        cname = f'{fn["name"]}#c{ci}'
        if stage_cb is not None:
            stage_cb(f'chunk {ci}/{len(chunks)}')
        cfp = hashlib.md5(ct.encode('utf-8')).hexdigest()
        cp = (doc.load_record(cfg['data_dir'], f['relpath'], 'chunk', cname,
                              fn['line'], cfp) if skip else None)
        if cp is None:
            cctx = (
                f"Symbol: {fn.get('qualified') or fn['name']} "
                f"(lines {fn['line']}-{fn.get('end_line') or fn['line']}), "
                f"file {f['relpath']}\n"
                f"Parameters: {', '.join(fn.get('params') or []) or '(none)'}"
                + (' + varargs' if fn.get('vararg') else '')
                + f"\nBody part {ci}/{len(chunks)} of a long function:\n"
                  + f"```{fence_lang(f['relpath'])}\n{ct}\n```")
            cp = doc.generate(client, 'chunk', prompts.get('chunk', ''),
                              cctx, retry)
            doc.save_record(cfg['data_dir'], f['relpath'], 'chunk', cname,
                            fn['line'], cp, cfp,
                            {'file': f['relpath'], 'fn': fn['name'],
                             'part': ci})
        notes.append(cp.get('summary', ''))
    return ('The body is long; it was summarized part by part:\n'
            + '\n'.join(f'{k}. {s}' for k, s in enumerate(notes, 1))
            + '\nDescribe the WHOLE function, synthesizing these parts.')


def _graph_names(g, node_id):
    outs, ins = [], []
    for u, v, d in g.edges(data=True):
        if d.get('type') != 'CALLS':
            continue
        if u == node_id:
            t = g.nodes[v]
            outs.append(t.get('name') or v)
        elif v == node_id:
            s = g.nodes[u]
            ins.append(s.get('qualified') or s.get('name') or u)
    return ins, outs


def llm_phase(cfg: dict, files, g):
    doccfg = cfg['documentation']
    if not (doccfg.get('generate_function_docs') or
            doccfg.get('generate_variable_docs') or
            doccfg.get('generate_file_summaries')):
        return 0
    prompts = {}
    for k, v in cfg['prompts'].items():
        try:
            with open(v, 'r', encoding='utf-8') as fh:
                prompts[k] = fh.read()
        except OSError:
            log(f'  missing prompt file: {v}')
    client = doc.LLMClient(cfg['llm'])
    retry = int(doccfg.get('retry_invalid_json', 2))
    skip = bool(doccfg.get('skip_existing', True))
    include_anon = bool(doccfg.get('include_anonymous_functions', False))
    ordered = sorted(files, key=lambda f: -len(f.get('functions') or []))
    maxlines = int(doccfg.get('max_function_lines') or 0)
    maxchunk = int(doccfg.get('max_chunk_lines') or 0) or 4000
    chunktok = int(doccfg.get('chunk_target_tokens') or 0)
    cpt = int(doccfg.get('chars_per_token') or 4)

    # ---- build a flat, deterministic job list ---------------------------
    jobs = []
    if doccfg.get('generate_function_docs'):
        tasks = [(f, fn) for f in ordered
                 for fn in f.get('functions') or []
                 if include_anon or fn['name'] != 'anon']
        nchunked = sum(1 for _, fn in tasks if maxlines and fn_length(fn) > maxlines)
        log(f'function docs: {len(tasks)} tasks ({nchunked} via chunk-and-merge)')
        for f, fn in tasks:
            jobs.append({'kind': 'function', 'f': f, 'sym': fn,
                         'nid': gmod.node_id_fn(f['relpath'], fn['name'], fn['line']),
                         'tag': f'{f["relpath"]}::{fn["name"]}@{fn["line"]}'})
    if doccfg.get('generate_variable_docs'):
        tasks = [(f, v) for f in ordered for v in f.get('file_vars') or []]
        log(f'variable docs: {len(tasks)} tasks')
        for f, v in tasks:
            jobs.append({'kind': 'variable', 'f': f, 'sym': v,
                         'tag': f'{f["relpath"]}::{v["name"]}@{v["line"]}'})
    if doccfg.get('generate_file_summaries'):
        tasks = list(ordered)
        log(f'file summaries: {len(tasks)} tasks')
        for f in tasks:
            jobs.append({'kind': 'summary', 'f': f,
                         'sym': {'name': 'file', 'line': 1}, 'tag': f['relpath']})
    if not jobs:
        return 0

    # ---- run the jobs on N parallel agents ------------------------------
    n = max(1, int(cfg.get('concurrency') or 2))
    tcfg = cfg.get('tui') or {}
    kind_label = {'function': 'functions', 'variable': 'variables',
                  'summary': 'files'}
    kinds = {}
    for lab, k in (('files', 'summary'), ('functions', 'function'),
                   ('variables', 'variable')):
        cnt = sum(1 for j in jobs if j['kind'] == k)
        if cnt:
            kinds[lab] = cnt
    tui = TUI(enabled=bool(tcfg.get('enabled', True)),
              interval=float(tcfg.get('interval') or 0.5),
              worker_count=n, total=len(jobs), kinds=kinds)
    tui.start()
    set_log_sink(tui.sink if tui.active else None)

    wid_map, wid_lock = {}, threading.Lock()

    def wid():
        ident = threading.get_ident()
        with wid_lock:
            if ident not in wid_map:
                wid_map[ident] = len(wid_map) + 1
            return wid_map[ident]

    def run(job):
        w, f, sym = wid(), job['f'], job['sym']
        tag, rel, name = job['tag'], f['relpath'], sym['name']
        fp = gmod.fingerprint([f])
        tui.job_start(w, rel, name)
        t0 = time.time()
        try:
            cached = False
            if job['kind'] == 'function':
                prose = (doc.load_record(cfg['data_dir'], rel, 'function',
                                         name, sym['line'], fp) if skip else None)
                cached = prose is not None
                if prose is None:
                    if maxlines and fn_length(sym) > maxlines:
                        report = lambda stage: tui.stage(w, rel, name, stage)
                        body_note = chunk_notes(client, cfg, f, sym, prompts,
                                                retry, skip, maxchunk, chunktok,
                                                cpt, stage_cb=report)
                        report('merge')
                        ctx = doc.fn_context_text(
                            {**sym, 'relpath': rel}, *_graph_names(g, job['nid']),
                            cfg['context'], body_note=body_note)
                    else:
                        tui.stage(w, rel, name, 'describe')
                        ctx = doc.fn_context_text(
                            {**sym, 'relpath': rel}, *_graph_names(g, job['nid']),
                            cfg['context'])
                    prose = doc.generate(client, 'function',
                                         prompts.get('function', ''), ctx, retry)
                doc.save_record(cfg['data_dir'], rel, 'function', name,
                                sym['line'], prose, fp,
                                {'id': job['nid'],
                                 'qualified': sym.get('qualified'),
                                 'params': sym.get('params'),
                                 'vararg': sym.get('vararg')})
            elif job['kind'] == 'variable':
                prose = (doc.load_record(cfg['data_dir'], rel, 'variable',
                                         name, sym['line'], fp) if skip else None)
                cached = prose is not None
                if prose is None:
                    tui.stage(w, rel, name, 'describe')
                    ctx = doc.var_context_text({**sym, 'relpath': rel},
                                               cfg['context'])
                    prose = doc.generate(client, 'variable',
                                         prompts.get('variable', ''), ctx, retry)
                doc.save_record(cfg['data_dir'], rel, 'variable', name,
                                sym['line'], prose, fp,
                                {'file': rel, 'name': name, 'line': sym['line'],
                                 'init': sym.get('init')})
            else:  # file summary
                prose = (doc.load_record(cfg['data_dir'], rel, 'summary',
                                         'file', 1, fp) if skip else None)
                cached = prose is not None
                if prose is None:
                    tui.stage(w, rel, 'file', 'describe')
                    ctx = doc.summary_context_text(f, cfg['context'])
                    prose = doc.generate(client, 'summary',
                                         prompts.get('summary', ''), ctx, retry)
                doc.save_record(cfg['data_dir'], rel, 'summary', 'file', 1,
                                prose, fp,
                                {'file': rel, 'lines': f.get('lines'),
                                 'function_count': len(f.get('functions') or [])})
            tui.job_end(w, time.time() - t0, generated=not cached,
                        failed=False, kind=kind_label.get(job['kind']))
            log(f'  {tag} OK' + (' (cached)' if cached else ''))
        except Exception as e:  # noqa: BLE001
            tui.job_end(w, time.time() - t0, generated=False, failed=True,
                        kind=kind_label.get(job['kind']))
            log(f'  {tag} FAILED: {e}')

    t_start = time.time()
    ex = ThreadPoolExecutor(max_workers=n)
    try:
        list(ex.map(run, jobs))
    except KeyboardInterrupt:
        # cancel everything still queued; let the in-flight tasks (at most
        # n) finish so their records get saved
        ex.shutdown(wait=True, cancel_futures=True)
        s = tui.snapshot()
        log(f'interrupted: {s["done"]}/{len(jobs)} tasks done, '
            f'failed={s["failed"]} — saved records kept; rerun to continue')
        raise
    finally:
        tui.stop()
        set_log_sink(None)
    s = tui.snapshot()
    log(f'llm phase: done={s["done"]} skipped={s["skipped"]} '
        f'failed={s["failed"]} in {time.time() - t_start:.0f}s '
        f'with {n} agent{"s" if n != 1 else ""}')
    return s['failed']


# ----------------------------------------------------------------- render

def render_all(cfg: dict, files, g):
    fn_recs = doc.list_records(cfg['data_dir'], 'function')
    var_recs = doc.list_records(cfg['data_dir'], 'variable')
    sum_recs = doc.list_records(cfg['data_dir'], 'summary')
    count = 0
    for f in files:
        finfo = {
            'relpath': f['relpath'],
            'lines': f.get('lines'),
            'functions': f.get('functions') or [],
            'file_vars': f.get('file_vars') or [],
        }
        summary = sum_recs.get((f['relpath'], 'file', 1))
        if summary:
            summary = summary.get('prose')
        out = doc.render_file_md(finfo, fn_recs, var_recs, summary,
                                 cfg['output_dir'], g)
        doc.write_md(out, cfg['output_dir'], f['relpath'])
        count += 1
    index = doc.render_index(files, cfg['output_dir'])
    ipath = os.path.join(cfg['output_dir'], 'index.md')
    os.makedirs(cfg['output_dir'], exist_ok=True)
    with open(ipath, 'w', encoding='utf-8') as fh:
        fh.write(index)
    log(f'rendered {count} file pages + index -> {cfg["output_dir"]}')

    if cfg.get('copy_meta'):
        meta_dir = os.path.join(cfg['output_dir'], 'meta')
        copied = []
        for name in ('graph.json', 'symbols.json'):
            src = os.path.join(cfg['data_dir'], name)
            if os.path.exists(src):
                os.makedirs(meta_dir, exist_ok=True)
                shutil.copy2(src, os.path.join(meta_dir, name))
                copied.append(name)
        if copied:
            log(f'copied {", ".join(copied)} -> {meta_dir}')


# -------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description='doc_maker')
    ap.add_argument('--config', default='settings.yaml')
    ap.add_argument('--fresh', action='store_true',
                    help='ignore analysis cache')
    ap.add_argument('--no-llm', action='store_true',
                    help='skip the LLM phase entirely')
    ap.add_argument('--purge', action='store_true',
                    help='delete docs/meta/data (output + data dirs) and exit')
    ap.add_argument('--regenerate', action='store_true',
                    help='delete docs/meta/data, then run everything fresh')
    args = ap.parse_args()
    if args.purge and args.regenerate:
        raise SystemExit('--purge and --regenerate are mutually exclusive')

    cfg = load_config(args.config)
    log(f'source: {cfg["source_dir"]}')
    files, skipped = scan_files(cfg)
    log(f'scanned {len(files)} files '
        f'({sum(len(v) for v in skipped.values())} skipped)')

    if args.purge or args.regenerate:
        if not purge_outputs(cfg):
            log('nothing to purge (no output/data directories found)')
        if args.purge:
            log('purged, nothing else to do')
            return

    stale = check_doc_cache(cfg, files)

    fp = scan_fingerprint(files)
    cached, cfp = (None, None) if (args.fresh or stale) else load_symbols(cfg)
    if cached is not None and cfp == fp:
        analysis = cached
        log(f'loaded analysis cache ({len(analysis)} files, fp={cfp[:12]})')
    else:
        analysis, ok, bad, binary = analyze_files(cfg, files)
        log(f'analysis: ok={ok} failed={bad} binary_skipped={binary}')
        save_symbols(cfg, analysis, fp)

    g = gmod.build_graph(analysis)
    gpath = os.path.join(cfg['data_dir'], 'graph.json')
    gmod.save_graph(g, gpath)
    log(f'graph: {g.number_of_nodes()} nodes / {g.number_of_edges()} edges '
        f'-> {gpath}')

    report_scan(cfg, analysis, skipped)

    failed = 0
    if args.no_llm:
        log('skipping LLM phase (--no-llm)')
    else:
        failed = llm_phase(cfg, analysis, g)

    render_all(cfg, analysis, g)
    if failed:
        log(f'NOT updating .doc_cache ({failed} failed task(s) this run; '
            f'unchanged cached records still reused next time)')
    else:
        write_doc_cache(cfg, files)
    log('done')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log('')
        log('interrupted by user — saved docs and records kept; '
            '.doc_cache not updated; rerun to continue where it left off')
        raise SystemExit(130)
