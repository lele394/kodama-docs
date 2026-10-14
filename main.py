"""kodama-docs — deterministic Lua documentation generator.

Pipeline: SCAN -> PARSE/EXTRACT -> GRAPH -> (LLM PROSE) -> MARKDOWN.
Everything except the LLM prose strings is plain Python. This entry point
only wires the phases together; the phases live in their own modules
(config, scan, outputs, llm_phase, records, context, markdown, llm).
"""
import argparse
import json
import os
import shutil

import backends
import kodama_docs.graph as gmod
from kodama_docs.config import load_config
from kodama_docs.llm_phase import llm_phase
from kodama_docs.markdown import (build_call_indexes, render_file_md,
                                  render_index, symbol_index, write_md)
from kodama_docs.outputs import check_doc_cache, purge_outputs, write_doc_cache
from kodama_docs.records import list_records
from kodama_docs.scan import (analyze_files, load_symbols, report_scan,
                  save_diagnostics, save_symbols,
                  scan_files, scan_fingerprint)
from kodama_docs.testing import test_backend
from kodama_docs.util import log


def _print_backend(b: dict):
    status = {'ready': 'green', 'unavailable': 'yellow',
              'invalid': 'red', 'conflict': 'red'}
    print(f"  {b['name']}  {b['version']}  api={b['api_version']}  "
          f"ext={','.join(b['extensions']) or '-'}  "
          f"status={b['status']} ({status.get(b['status'], 'white')})")
    if b['description']:
        print(f"      {b['description']}")
    for iss in b['issues']:
        print(f'      ! {iss}')


def _print_backends(bs):
    print(f'backends ({len(bs)}):')
    for b in bs:
        _print_backend(b)
    ready = [b for b in bs if b['status'] == 'ready']
    exts = sorted(e for b in ready for e in b['extensions'])
    print(f'routing: {", ".join(exts) or "-"}')


def render_all(cfg: dict, files, g, diag=None, astatus=None):
    fn_recs = list_records(cfg['data_dir'], 'function')
    var_recs = list_records(cfg['data_dir'], 'variable')
    sum_recs = list_records(cfg['data_dir'], 'summary')
    # One O(E) pass over the graph for the whole render, instead of a full
    # edge scan per function (O(F×E) — the 10+ minute render tail).
    call_idx = build_call_indexes(g)
    sym_idx = symbol_index(g)
    count = 0
    for f in files:
        finfo = {
            'relpath': f['relpath'],
            'lines': f.get('lines'),
            'functions': f.get('functions') or [],
            'file_vars': f.get('file_vars') or [],
            'classes': f.get('classes') or [],
        }
        summary = sum_recs.get((f['relpath'], 'file', 1))
        if summary:
            summary = summary.get('prose')
        out = render_file_md(finfo, fn_recs, var_recs, summary,
                             cfg['output_dir'], g, call_idx, sym_idx,
                             diag=diag)
        write_md(out, cfg['output_dir'], f['relpath'])
        count += 1
    index = render_index(files, cfg['output_dir'],
                         diag=diag, astatus=astatus,
                         rs=gmod.resolution_summary(g))
    ipath = os.path.join(cfg['output_dir'], 'index.md')
    os.makedirs(cfg['output_dir'], exist_ok=True)
    with open(ipath, 'w', encoding='utf-8') as fh:
        fh.write(index)
    log(f'rendered {count} file pages + index -> {cfg["output_dir"]}')

    if cfg.get('copy_meta'):
        meta_dir = os.path.join(cfg['output_dir'], 'meta')
        copied = []
        for name in ('graph.json', 'symbols.json', 'diagnostics.json'):
            src = os.path.join(cfg['data_dir'], name)
            if os.path.exists(src):
                os.makedirs(meta_dir, exist_ok=True)
                shutil.copy2(src, os.path.join(meta_dir, name))
                copied.append(name)
        if copied:
            log(f'copied {", ".join(copied)} -> {meta_dir}')


def main():
    ap = argparse.ArgumentParser(description='kodama-docs')
    ap.add_argument('command', nargs='?', choices=[None, 'test-backend'],
                    help="subcommand: 'test-backend' runs a backend's "
                         "self-test against its own test codebase; omit for "
                         "a normal documentation run")
    ap.add_argument('--backend', metavar='NAME',
                    help='backend name for test-backend (e.g. python)')
    ap.add_argument('--config', default='settings.yaml')
    ap.add_argument('--fresh', action='store_true',
                    help='ignore analysis cache')
    ap.add_argument('--no-llm', action='store_true',
                    help='skip the LLM model calls only (stub prose cached; '
                         'all deterministic sections are still generated)')
    ap.add_argument('--purge', action='store_true',
                    help='delete docs/meta/data (output + data dirs) and exit')
    ap.add_argument('--regenerate', action='store_true',
                    help='delete docs/meta/data, then run everything fresh')
    ap.add_argument('--serve', action='store_true',
                    help='serve the rendered docs over HTTP instead of '
                         'generating (needs a previous run)')
    # backend management (mutually exclusive with a pipeline run)
    ap.add_argument('--list-backends', action='store_true',
                    help='list installed backends (status + requirements) '
                         'and exit')
    ap.add_argument('--install', metavar='URL',
                    help='install a backend from a git URL (or local path): '
                         'clones it into backends/ and installs its python '
                         'requirements (runs third-party code — review first)')
    ap.add_argument('--remove', metavar='NAME',
                    help='remove an installed backend by manifest name')
    args = ap.parse_args()
    if args.purge and args.regenerate:
        raise SystemExit('--purge and --regenerate are mutually exclusive')
    if sum(bool(x) for x in (args.list_backends, args.install, args.remove)) \
            > 1:
        raise SystemExit('--list-backends / --install / --remove are '
                         'mutually exclusive')

    if args.list_backends or args.install or args.remove:
        if args.install is not None:
            rep = backends.install_backend(args.install)
            for ok, msg in rep['steps']:
                log(('install: ' if ok else 'install (failed): ') + msg)
            print()
            for b in backends.list_backends():
                if b['dir'] == rep['dir']:
                    _print_backend(b)
            return
        if args.remove is not None:
            d = backends.remove_backend(args.remove)
            log(f'remove: deleted backends/{d}')
            return
        bs = backends.list_backends()
        if not bs:
            log('no backends installed (backends/ has no manifest.toml '
                'subdirectories)')
            return
        _print_backends(bs)
        return

    if args.command == 'test-backend':
        if args.backend is None:
            raise SystemExit('test-backend needs --backend NAME '
                             '(e.g. --backend python)')
        rc = test_backend(args.backend)
        raise SystemExit(rc)

    cfg = load_config(args.config)

    if args.serve:
        from web import server as webserver
        webdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'web')
        ws = webserver.load_settings(os.path.join(webdir, 'web_settings.yaml'))
        webserver.serve(ws['docs_dir'] or cfg['output_dir'], ws, webdir)
        return

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
    cached, cfp, cback = (None, None, None) \
        if (args.fresh or stale) else load_symbols(cfg)
    if cached is not None and cfp == fp and \
            backends.backends_compatible(cached, cback):
        analysis = cached
        log(f'loaded analysis cache ({len(analysis)} files, fp={cfp[:12]})')
        # Per-file analysis status from the last run's diagnostics.json
        # (files that failed/binary previously are still visible, P0-3).
        astatus = {f['relpath']: {'status': 'ok'} for f in analysis}
        dpath = os.path.join(cfg['data_dir'], 'diagnostics.json')
        try:
            with open(dpath, 'r', encoding='utf-8') as fh:
                d = json.load(fh)
            if d.get('fingerprint') == fp:
                astatus = d['analysis']['files']
        except (OSError, ValueError, KeyError):
            pass
    else:
        if cached is not None and cfp == fp:
            log('analysis cache stale (backends changed); re-extracting')
        analysis, astatus = analyze_files(cfg, files)
        nfail = sum(1 for v in astatus.values() if v['status'] == 'failed')
        nbin = sum(1 for v in astatus.values() if v['status'] == 'binary')
        log(f'analysis: ok={len(analysis)} failed={nfail} '
            f'binary_skipped={nbin}')
        save_symbols(cfg, analysis, fp)

    g, diag = gmod.build_graph(analysis)
    gpath = os.path.join(cfg['data_dir'], 'graph.json')
    gmod.save_graph(g, gpath)
    log(f'graph: {g.number_of_nodes()} nodes / {g.number_of_edges()} edges '
        f'-> {gpath}')

    save_diagnostics(cfg['data_dir'], fp, astatus, diag, g)

    report_scan(cfg, analysis, skipped, g, diag, astatus)

    failed = llm_phase(cfg, analysis, g, no_llm=args.no_llm)

    render_all(cfg, analysis, g, diag, astatus)
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
