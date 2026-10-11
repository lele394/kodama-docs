"""doc_maker — deterministic Lua documentation generator.

Pipeline: SCAN -> PARSE/EXTRACT -> GRAPH -> (LLM PROSE) -> MARKDOWN.
Everything except the LLM prose strings is plain Python. This entry point
only wires the phases together; the phases live in their own modules
(config, scan, outputs, llm_phase, records, context, markdown, llm).
"""
import argparse
import os
import shutil

import graph as gmod
from config import load_config
from llm_phase import llm_phase
from markdown import render_file_md, render_index, write_md
from outputs import check_doc_cache, purge_outputs, write_doc_cache
from records import list_records
from scan import (analyze_files, load_symbols, report_scan, save_symbols,
                  scan_files, scan_fingerprint)
from util import log


def render_all(cfg: dict, files, g):
    fn_recs = list_records(cfg['data_dir'], 'function')
    var_recs = list_records(cfg['data_dir'], 'variable')
    sum_recs = list_records(cfg['data_dir'], 'summary')
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
        out = render_file_md(finfo, fn_recs, var_recs, summary,
                             cfg['output_dir'], g)
        write_md(out, cfg['output_dir'], f['relpath'])
        count += 1
    index = render_index(files, cfg['output_dir'])
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
    ap.add_argument('--serve', action='store_true',
                    help='serve the rendered docs over HTTP instead of '
                         'generating (needs a previous run)')
    args = ap.parse_args()
    if args.purge and args.regenerate:
        raise SystemExit('--purge and --regenerate are mutually exclusive')

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
