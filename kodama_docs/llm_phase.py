"""LLM phase: build the deterministic job list and run it on N parallel
agents (each job cached separately via records). Returns the failure count.
"""
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import kodama_docs.graph as gmod
from kodama_docs.context import (fn_chunks, fn_context_text, var_context_text,
                     summary_context_text)
from kodama_docs.llm import LLMClient, generate
from kodama_docs.records import load_record, save_record
from kodama_docs.tui import TUI
from kodama_docs.util import fence_lang, log, set_log_sink


def fn_length(fn: dict) -> int:
    return (fn.get('end_line') or fn['line']) - fn['line'] + 1


def chunk_notes(client, cfg, f, fn, prompts, retry, skip,
                maxchunk, chunktok, cpt=4, stage_cb=None):
    """Summarize a long function body part by part (each part cached
    separately) and return the body_note text for the merge prompt."""
    chunks = fn_chunks(fn.get('body') or '', maxchunk, chunktok, cpt)
    if not chunks:
        return 'Source: (empty body)'
    notes = []
    for ci, ct in enumerate(chunks, 1):
        cname = f'{fn["name"]}#c{ci}'
        if stage_cb is not None:
            stage_cb(f'chunk {ci}/{len(chunks)}')
        cfp = hashlib.md5(ct.encode('utf-8')).hexdigest()
        cp = (load_record(cfg['data_dir'], f['relpath'], 'chunk', cname,
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
            cp = generate(client, 'chunk', prompts.get('chunk', ''),
                          cctx, retry)
            save_record(cfg['data_dir'], f['relpath'], 'chunk', cname,
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
    client = LLMClient(cfg['llm'])
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
        for f in ordered:
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
                prose = (load_record(cfg['data_dir'], rel, 'function',
                                     name, sym['line'], fp) if skip else None)
                cached = prose is not None
                if prose is None:
                    if maxlines and fn_length(sym) > maxlines:
                        report = lambda stage: tui.stage(w, rel, name, stage)
                        body_note = chunk_notes(client, cfg, f, sym, prompts,
                                                retry, skip, maxchunk, chunktok,
                                                cpt, stage_cb=report)
                        report('merge')
                        ctx = fn_context_text(
                            {**sym, 'relpath': rel}, *_graph_names(g, job['nid']),
                            cfg['context'], body_note=body_note)
                    else:
                        tui.stage(w, rel, name, 'describe')
                        ctx = fn_context_text(
                            {**sym, 'relpath': rel}, *_graph_names(g, job['nid']),
                            cfg['context'])
                    prose = generate(client, 'function',
                                     prompts.get('function', ''), ctx, retry)
                save_record(cfg['data_dir'], rel, 'function', name,
                            sym['line'], prose, fp,
                            {'id': job['nid'],
                             'qualified': sym.get('qualified'),
                             'params': sym.get('params'),
                             'vararg': sym.get('vararg')})
            elif job['kind'] == 'variable':
                prose = (load_record(cfg['data_dir'], rel, 'variable',
                                     name, sym['line'], fp) if skip else None)
                cached = prose is not None
                if prose is None:
                    tui.stage(w, rel, name, 'describe')
                    ctx = var_context_text({**sym, 'relpath': rel},
                                           cfg['context'])
                    prose = generate(client, 'variable',
                                     prompts.get('variable', ''), ctx, retry)
                save_record(cfg['data_dir'], rel, 'variable', name,
                            sym['line'], prose, fp,
                            {'file': rel, 'name': name, 'line': sym['line'],
                             'init': sym.get('init')})
            else:  # file summary
                prose = (load_record(cfg['data_dir'], rel, 'summary',
                                     'file', 1, fp) if skip else None)
                cached = prose is not None
                if prose is None:
                    tui.stage(w, rel, 'file', 'describe')
                    ctx = summary_context_text(f, cfg['context'])
                    prose = generate(client, 'summary',
                                     prompts.get('summary', ''), ctx, retry)
                save_record(cfg['data_dir'], rel, 'summary', 'file', 1,
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
