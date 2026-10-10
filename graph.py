"""Deterministic cross-file graph builder (networkx MultiDiGraph).

Node kinds: file, function, variable, builtin, external, module.
Edge kinds: CONTAINS (file -> fn/var), CALLS (fn/file -> fn/ext/builtin),
IMPORTS (file -> file/module).
"""
import hashlib
import json
import os

import networkx as nx

from analyzer import BUILTIN_NAMES

BUILTIN_SET = set(BUILTIN_NAMES)


def node_id_file(relpath):
    return 'file:' + relpath


def node_id_fn(relpath, name, line):
    return f'fn:{relpath}::{name}@{line}'


def node_id_var(relpath, name, line):
    return f'var:{relpath}::{name}@{line}'


def fingerprint(files):
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x['relpath']):
        h.update(f['relpath'].encode('utf-8'))
        h.update(str(len(f.get('functions') or [])).encode())
        if f.get('size') is not None:
            h.update(str(f['size']).encode())
    return h.hexdigest()


def build_graph(files):
    """files: list of per-file dicts with relpath/lines/functions/file_vars/calls."""
    g = nx.MultiDiGraph()
    edge_keys = set()

    def add_edge(src, tgt, etype, **attrs):
        key = (src, tgt, etype)
        if key in edge_keys:
            return
        edge_keys.add(key)
        g.add_edge(src, tgt, type=etype, **attrs)

    # ---- pass 1: nodes -------------------------------------------------
    qual_map = {}   # qualified name -> fn id
    short_map = {}  # last segment  -> [fn ids]
    for f in files:
        rp = f['relpath']
        fid = node_id_file(rp)
        g.add_node(fid, kind='file', relpath=rp,
                   lines=f.get('lines'),
                   function_count=len(f.get('functions') or []),
                   variable_count=len(f.get('file_vars') or []))
        for fn in f.get('functions') or []:
            nid = node_id_fn(rp, fn['name'], fn['line'])
            g.add_node(nid, kind='function', relpath=rp, name=fn['name'],
                       qualified=fn.get('qualified') or fn['name'],
                       line=fn['line'], end_line=fn.get('end_line', fn['line']),
                       params=list(fn.get('params') or []),
                       vararg=bool(fn.get('vararg')), file_id=fid,
                       body=fn.get('body', ''))
            add_edge(fid, nid, 'CONTAINS')
            qual = fn.get('qualified') or fn['name']
            if qual and qual not in qual_map:
                qual_map[qual] = nid
            short_map.setdefault(fn['name'], []).append(nid)
        for v in f.get('file_vars') or []:
            vid = node_id_var(rp, v['name'], v['line'])
            g.add_node(vid, kind='variable', relpath=rp, name=v['name'],
                       line=v['line'], init=v.get('init', 'expr'),
                       file_id=fid)
            add_edge(fid, vid, 'CONTAINS')
    for ids in short_map.values():
        ids.sort()

    # ---- pass 2: edges --------------------------------------------------
    known_files = {f['relpath'] for f in files}

    def resolve_callee(name):
        if name in qual_map:
            return qual_map[name]
        last = name.rsplit('.', 1)[-1]
        cands = short_map.get(last)
        if cands:
            return cands[0]
        if name in BUILTIN_SET:
            return 'builtin:' + name
        return 'ext:' + name

    for f in files:
        rp = f['relpath']
        fid = node_id_file(rp)
        fns = f.get('functions') or []

        def owner(call_line):
            best = None
            for fn in fns:
                if fn['line'] <= call_line <= fn.get('end_line', fn['line']):
                    span = fn.get('end_line', fn['line']) - fn['line']
                    if best is None or span < best[0]:
                        best = (span, fn)
            return best[1] if best else None

        for c in f.get('calls') or []:
            tgt = resolve_callee(c['callee'])
            if not g.has_node(tgt) and any(
                    tgt.startswith(p) for p in ('builtin:', 'ext:', 'mod:')):
                kind, nm = tgt.split(':', 1)
                g.add_node(tgt, kind=kind, name=nm)
            src = fid
            fn = owner(c['line'])
            if fn is not None:
                src = node_id_fn(rp, fn['name'], fn['line'])
            add_edge(src, tgt, 'CALLS', line=c['line'])

        for imp in f.get('imports') or []:
            mod = imp['module']
            cands = [mod + '.lua', mod + '/init.lua',
                     mod.replace('.', '/') + '.lua',
                     mod.replace('.', '/') + '/init.lua']
            hit = next((c for c in cands if c in known_files), None)
            if hit:
                add_edge(fid, node_id_file(hit), 'IMPORTS',
                         line=imp['line'], module=mod)
            else:
                tgt = 'mod:' + mod
                if not g.has_node(tgt):
                    g.add_node(tgt, kind='module', name=mod)
                add_edge(fid, tgt, 'IMPORTS', line=imp['line'], module=mod)

    return g


def save_graph(g, path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    data = nx.node_link_data(g, edges='edges')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def load_graph(path):
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    g = nx.node_link_graph(data, edges='edges', multigraph=True)
    return g
