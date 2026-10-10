"""doc_maker — deterministic Lua documentation generator.

Pipeline: SCAN -> PARSE/EXTRACT -> GRAPH -> (LLM PROSE) -> MARKDOWN.
Everything except the LLM prose strings is plain Python.
"""
import argparse
import hashlib
import json
import os
import shutil

import ruamel.yaml

from util import log
import backends
import graph as gmod
import documentation as doc


# ------------------------------------------------------------------ config

def load_config(path: str) -> dict:
    yaml = ruamel.yaml.YAML()
    with open(path, 'r', encoding='utf-8') as fh:
        raw = yaml.load(fh)
    base = os.path.dirname(os.path.abspath(path))

    def rp(p):
        p = str(p)
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    return {
        'source_dir': rp(raw['project']['source_dir']),
        'output_dir': rp(raw['project']['output_dir']),
        'data_dir': rp(raw['project']['data_dir']),
        'exclude': [str(x) for x in (raw['project'].get('exclude') or [])],
        'max_file_bytes': int(raw['project'].get('max_file_bytes', 26214400)),
        'llm': dict(raw.get('llm') or {}),
        'context': dict(raw.get('context') or {}),
        'documentation': dict(raw.get('documentation') or {}),
        'copy_meta': bool(raw['project'].get('copy_meta', False)),
        'prompts': {k: rp(v) for k, v in (raw.get('prompts') or {}).items()},
    }


def scan_files(cfg: dict):
    excl = set(cfg['exclude'])
    exts = set(backends.EXTRACTORS)
    out = []
    for dirpath, dirnames, filenames in os.walk(cfg['source_dir']):
        dirnames[:] = sorted(d for d in dirnames if d not in excl)
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1].lower() not in exts:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, cfg['source_dir']).replace('\\', '/')
            if any(part in excl for part in rel.split('/')):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > cfg['max_file_bytes']:
                continue
            out.append({'full': full, 'relpath': rel, 'size': size})
    return out


def scan_fingerprint(files) -> str:
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x['relpath']):
        h.update(f['relpath'].encode('utf-8'))
        h.update(str(f['size']).encode('utf-8'))
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


# ---------------------------------------------------------------- LLM phase

def fn_length(fn: dict) -> int:
    return (fn.get('end_line') or fn['line']) - fn['line'] + 1


def chunk_notes(client, cfg, f, fn, prompts, retry, skip,
                maxchunk, chunktok, cpt=4):
    """Summarize a long function body part by part (each part cached
    separately) and return the body_note text for the merge prompt."""
    chunks = doc.fn_chunks(fn.get('body') or '', maxchunk, chunktok, cpt)
    if not chunks:
        return 'Source: (empty body)'
    notes = []
    for ci, ct in enumerate(chunks, 1):
        cname = f'{fn["name"]}#c{ci}'
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
                  + f"```lua\n{ct}\n```")
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
        return
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
    stats = {'done': 0, 'skipped': 0, 'failed': 0}

    def one(kind, f, sym, ctx, symbol):
        fp = gmod.fingerprint([f])
        if skip:
            prose = doc.load_record(cfg['data_dir'], f['relpath'], kind,
                                    sym['name'], sym['line'], fp)
            if prose is not None:
                stats['skipped'] += 1
                return
        prose = doc.generate(client, kind, prompts.get(kind, ''), ctx, retry)
        doc.save_record(cfg['data_dir'], f['relpath'], kind, sym['name'],
                        sym['line'], prose, fp, symbol)
        stats['done'] += 1

    # ---- functions ----------------------------------------------------
    if doccfg.get('generate_function_docs'):
        maxlines = int(doccfg.get('max_function_lines') or 0)
        maxchunk = int(doccfg.get('max_chunk_lines') or 0) or 4000
        chunktok = int(doccfg.get('chunk_target_tokens') or 0)
        cpt = int(doccfg.get('chars_per_token') or 4)
        tasks = []
        for f in ordered:
            for fn in f.get('functions') or []:
                if not include_anon and fn['name'] == 'anon':
                    continue
                tasks.append((f, fn))
        maxfn = int(doccfg.get('max_function_tasks') or 0)
        if maxfn:
            tasks = tasks[:maxfn]
        nchunked = sum(1 for f, fn in tasks if maxlines and fn_length(fn) > maxlines)
        log(f'function docs: {len(tasks)} tasks '
            f'({nchunked} via chunk-and-merge)')
        for i, (f, fn) in enumerate(tasks, 1):
            nid = gmod.node_id_fn(f['relpath'], fn['name'], fn['line'])
            fp = gmod.fingerprint([f])
            calls_in, calls_out = _graph_names(g, nid)
            fnfull = {**fn, 'relpath': f['relpath']}
            tag = f'{f["relpath"]}::{fn["name"]}@{fn["line"]}'
            try:
                prose = (doc.load_record(cfg['data_dir'], f['relpath'],
                                         'function', fn['name'], fn['line'], fp)
                         if skip else None)
                cached = prose is not None
                if prose is None:
                    if maxlines and fn_length(fn) > maxlines:
                        body_note = chunk_notes(
                            client, cfg, f, fn, prompts, retry, skip,
                            maxchunk, chunktok, cpt)
                        ctx = doc.fn_context_text(fnfull, calls_in, calls_out,
                                                  cfg['context'],
                                                  body_note=body_note)
                    else:
                        ctx = doc.fn_context_text(fnfull, calls_in, calls_out,
                                                  cfg['context'])
                    prose = doc.generate(client, 'function',
                                         prompts.get('function', ''),
                                         ctx, retry)
                doc.save_record(cfg['data_dir'], f['relpath'], 'function',
                                fn['name'], fn['line'], prose, fp,
                                {'id': nid, 'qualified': fn.get('qualified'),
                                 'params': fn.get('params'),
                                 'vararg': fn.get('vararg')})
                stats['skipped' if cached else 'done'] += 1
                log(f'  fn {i}/{len(tasks)} {tag} OK')
            except Exception as e:  # noqa: BLE001
                stats['failed'] += 1
                log(f'  fn {i}/{len(tasks)} {tag} FAILED: {e}')

    # ---- variables ------------------------------------------------------
    if doccfg.get('generate_variable_docs'):
        tasks = []
        for f in ordered:
            for v in f.get('file_vars') or []:
                tasks.append((f, v))
        maxv = int(doccfg.get('max_variable_tasks') or 0)
        if maxv:
            tasks = tasks[:maxv]
        log(f'variable docs: {len(tasks)} tasks')
        for i, (f, v) in enumerate(tasks, 1):
            ctx = doc.var_context_text({**v, 'relpath': f['relpath']},
                                       cfg['context'])
            try:
                one('variable', f, v, ctx,
                    {'file': f['relpath'], 'name': v['name'], 'line': v['line'],
                     'init': v.get('init')})
                log(f'  var {i}/{len(tasks)} {f["relpath"]}::{v["name"]} OK')
            except Exception as e:  # noqa: BLE001
                stats['failed'] += 1
                log(f'  var {i}/{len(tasks)} {f["relpath"]}::{v["name"]} FAILED: {e}')

    # ---- file summaries -------------------------------------------------
    if doccfg.get('generate_file_summaries'):
        tasks = list(ordered)
        maxs = int(doccfg.get('max_summary_tasks') or 0)
        if maxs:
            tasks = tasks[:maxs]
        log(f'file summaries: {len(tasks)} tasks')
        for i, f in enumerate(tasks, 1):
            sym = {'name': 'file', 'line': 1}
            ctx = doc.summary_context_text(f, cfg['context'])
            try:
                one('summary', f, sym, ctx,
                    {'file': f['relpath'], 'lines': f.get('lines'),
                     'function_count': len(f.get('functions') or [])})
                log(f'  sum {i}/{len(tasks)} {f["relpath"]} OK')
            except Exception as e:  # noqa: BLE001
                stats['failed'] += 1
                log(f'  sum {i}/{len(tasks)} {f["relpath"]} FAILED: {e}')

    log(f'llm phase: done={stats["done"]} skipped={stats["skipped"]} '
        f'failed={stats["failed"]}')


# ----------------------------------------------------------------- render

def render_all(cfg: dict, files):
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
                                 cfg['output_dir'])
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
    args = ap.parse_args()

    cfg = load_config(args.config)
    log(f'source: {cfg["source_dir"]}')
    files = scan_files(cfg)
    log(f'scanned {len(files)} files')

    fp = scan_fingerprint(files)
    cached, cfp = (None, None) if args.fresh else load_symbols(cfg)
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

    if args.no_llm:
        log('skipping LLM phase (--no-llm)')
    else:
        llm_phase(cfg, analysis, g)

    render_all(cfg, analysis)
    log('done')


if __name__ == '__main__':
    main()
