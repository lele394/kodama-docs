"""Deterministic cross-file graph builder (networkx MultiDiGraph).

Node kinds: file, function, variable, builtin, external, module.
Edge kinds: CONTAINS (file -> fn/var), CALLS (fn/file -> fn/ext/builtin),
 IMPORTS (file -> file/module), READS (fn -> var: the function body
references a file-level variable).

Resolution policy
-----------------
Callee resolution uses the CALLER file's context, in this order:

1. a function defined in the same file (lexical scope wins);
2. the caller's own name bindings: imports (``import x``,
   ``from x import n``, ``import x as a``) and module-alias variables
   (``local A = require('m')``) — when the bound name resolves to a
   project file that defines the target, the edge links there
   (status: resolved);
3. a builtin/stdlib name for the caller language (status: builtin);
4. a name occurring exactly once across the project (status: inferred —
   a documented inference, still shown in the docs);
5. a name occurring 2+ times in the project is AMBIGUOUS: NO edge is
   written, and the call site is recorded in the returned diagnostics;
6. anything else is external to this codebase (status: external — kept
   as a node so the docs can say "unresolved", never guessed).

Every CALLS edge carries a ``status`` attribute:
    resolved | inferred | builtin | external
Every IMPORTS edge carries:
    resolved | unresolved

Ambiguity is never silently resolved by picking a candidate: the docs
must be able to state what is known, what is inferred and what is
unresolved.
"""
import hashlib
import json
import os
import re

import networkx as nx

from backends import builtins_for, module_candidates


def node_id_file(relpath):
    return 'file:' + relpath


def node_id_fn(relpath, name, line):
    return f'fn:{relpath}::{name}@{line}'


def node_id_var(relpath, name, line):
    return f'var:{relpath}::{name}@{line}'


def _var_reads(body: str, name: str, is_py: bool) -> bool:
    """True if `body` references file variable `name`.

    A reference is a bare identifier use: `x.name` (method/namespace
    access) and longer identifiers never count. A reference is not
    counted when the function shadows the name itself — its own
    parameter, or a local declared/assigned in its body.
    """
    e = re.escape(name)
    if not re.search(r'(?<![\w.])' + e + r'(?!\w)', body):
        return False
    if is_py:
        shadowed = re.search(r'(?m)^\s*' + e + r'\s*=[^=]', body) \
            or re.search(r'\b' + e + r'\s*[-+*/%&|^]=', body)
    else:
        shadowed = re.search(r'\blocal\s+' + e + r'\b', body)
    return not shadowed


def fingerprint(files):
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x['relpath']):
        h.update(f['relpath'].encode('utf-8'))
        h.update(str(len(f.get('functions') or [])).encode())
        if f.get('size') is not None:
            h.update(str(f['size']).encode())
    return h.hexdigest()


def graph_neighbor_names(g, node_id):
    """(called_by, calls) name lists from a node's CALLS edges.

    Used both for the LLM context ("Called by:" / "Calls:") and for the
    record fingerprint, so cached prose is invalidated when the
    call-relationship set of a symbol changes."""
    ins, outs = [], []
    for u, v, data in g.edges(data=True):
        if data.get('type') != 'CALLS':
            continue
        if v == node_id:
            nm = g.nodes[u].get('name')
            if nm:
                ins.append(nm)
        if u == node_id:
            t = g.nodes.get(v)
            nm = t.get('name') if t else None
            if nm:
                outs.append(nm)
    return ins, outs


def _cand_display(nid: str) -> str:
    """Human-readable candidate form: 'fn:a.py::b@3' -> 'a.py::b@3'."""
    return nid.split(':', 1)[1] if nid.startswith('fn:') else nid


def build_graph(files):
    """files: list of per-file dicts with relpath/lines/functions/file_vars/calls.

    Returns (graph, diagnostics) where diagnostics is:
        {'ambiguous_calls':    [{file, line, name, candidates[]}, ...],
         'inferred_calls':     [{file, line, name}, ...],
         'external_calls':     [{file, line, name}, ...],
         'builtin_calls':      [{file, line, name}, ...],
         'unresolved_imports': [{file, line, module}, ...]}
    """
    g = nx.MultiDiGraph()
    edge_keys = set()

    def add_edge(src, tgt, etype, **attrs):
        # include the call/import line so every call site keeps its own edge
        key = (src, tgt, etype, attrs.get('line'))
        if key in edge_keys:
            return
        edge_keys.add(key)
        g.add_edge(src, tgt, type=etype, **attrs)

    diag = {'ambiguous_calls': [], 'inferred_calls': [],
            'external_calls': [], 'builtin_calls': [],
            'unresolved_imports': []}

    # ---- pass 1: nodes -------------------------------------------------
    qual_cands = {}  # qualified name -> [fn ids]
    name_cands = {}  # plain name     -> [fn ids]
    file_fn = {}     # (relpath, plain name) -> first fn id in that file
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
            qual_cands.setdefault(qual, []).append(nid)
            name_cands.setdefault(fn['name'], []).append(nid)
            if (rp, fn['name']) not in file_fn:
                file_fn[(rp, fn['name'])] = nid
        for v in f.get('file_vars') or []:
            vid = node_id_var(rp, v['name'], v['line'])
            g.add_node(vid, kind='variable', relpath=rp, name=v['name'],
                       line=v['line'], init=v.get('init', 'expr'),
                       file_id=fid)
            add_edge(fid, vid, 'CONTAINS')
    for ids in list(qual_cands.values()) + list(name_cands.values()):
        ids.sort()

    # ---- pass 2: edges ----------------------------------------------------
    known_files = {f['relpath'] for f in files}

    def mod_file(mod, from_rp):
        for c in module_candidates(mod, from_rp):
            if c in known_files:
                return c
        return None

    # Per-file name bindings: imports (with optional bind/name) plus
    # module-alias variables (Lua require / dofile).
    #   {'bind': local name, 'file': project file or None,
    #    'name': target symbol inside that module or None}
    binds = {}
    for f in files:
        rp = f['relpath']
        bs = []
        for imp in f.get('imports') or []:
            mod = imp.get('module')
            if not mod:
                continue
            bs.append({'bind': imp.get('bind') or mod.rsplit('.', 1)[-1],
                       'file': mod_file(mod, rp),
                       'name': imp.get('name')})
        for v in f.get('file_vars') or []:
            mod = v.get('module')
            if mod:
                bs.append({'bind': v['name'],
                           'file': mod_file(mod, rp),
                           'name': None})
        binds[rp] = bs

    def resolve(rp, name, method, line):
        """Resolve one call site using the context of file `rp`.

        Returns (target_node_id, status) or None when the candidates are
        ambiguous (the call site is recorded in diag; no edge is written).
        """
        file_bs = binds.get(rp, [])
        builtins = builtins_for(rp)
        label = f'{name}.{method}' if method else name

        def dedup(seq):
            # a file can bind the same name twice (e.g. a require recorded
            # as both an import and a module-alias var) — same target
            return list(dict.fromkeys(seq))

        def ambiguous(cands):
            cands = dedup(cands)
            diag['ambiguous_calls'].append({
                'file': rp, 'line': line, 'name': label,
                'candidates': [_cand_display(c) for c in cands]})
            return None

        if method and name:
            # 1) object bound to a project module in this file -> its method
            hits = []
            for b in file_bs:
                if b['bind'] == name and b['file']:
                    hit = file_fn.get((b['file'], method))
                    if hit:
                        hits.append(hit)
            if hits:
                hits = dedup(hits)
                return (hits[0], 'resolved') if len(hits) == 1 \
                    else ambiguous(hits)
            # 2) exact qualified name name.method defined in the project
            cands = qual_cands.get(f'{name}.{method}')
            if cands:
                return (cands[0], 'resolved') if len(cands) == 1 \
                    else ambiguous(cands)
            # 3) object (or its root) is a stdlib/builtin name — never
            #    guess a project function with the same method name
            if name in builtins or name.split('.', 1)[0] in builtins:
                return 'builtin:' + label, 'builtin'
            # 4) method name unique project-wide (unbound object, e.g. a
            #    local table instance) — documented inference
            cands = name_cands.get(method)
            if cands:
                return (cands[0], 'inferred') if len(cands) == 1 \
                    else ambiguous(cands)
            return 'ext:' + label, 'external'

        if '.' in name:
            base, _, rest = name.partition('.')
            # 1) base bound to a project module in this file
            hits = []
            for b in file_bs:
                if b['bind'] == base and b['file']:
                    hit = file_fn.get((b['file'], b['name'] or rest))
                    if hit:
                        hits.append(hit)
            if hits:
                hits = dedup(hits)
                return (hits[0], 'resolved') if len(hits) == 1 \
                    else ambiguous(hits)
            # 2) exact qualified name in the project
            cands = qual_cands.get(name)
            if cands:
                return (cands[0], 'resolved') if len(cands) == 1 \
                    else ambiguous(cands)
            # 3) builtin namespace (math.sqrt, io.open, os.path.join, ...)
            if base in builtins:
                return 'builtin:' + name, 'builtin'
            return 'ext:' + name, 'external'

        # bare name
        # 1) defined in the same file (lexical scope wins)
        local = file_fn.get((rp, name))
        if local:
            return local, 'resolved'
        # 2) bound by this file's imports to a project file
        #    (`from users import validate` then `validate()`)
        hits = []
        for b in file_bs:
            if b['bind'] == name and b['file'] and b['name']:
                hit = file_fn.get((b['file'], b['name']))
                if hit:
                    hits.append(hit)
        if hits:
            hits = dedup(hits)
            return (hits[0], 'resolved') if len(hits) == 1 \
                else ambiguous(hits)
        # 3) builtin
        if name in builtins:
            return 'builtin:' + name, 'builtin'
        # 4) name unique project-wide — documented inference
        cands = name_cands.get(name)
        if cands:
            return (cands[0], 'inferred') if len(cands) == 1 \
                else ambiguous(cands)
        return 'ext:' + name, 'external'

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
            res = resolve(rp, c['callee'], c.get('method'), c['line'])
            if res is None:  # ambiguous: diagnostic recorded, no edge
                continue
            tgt, status = res
            if not g.has_node(tgt) and tgt.startswith(('builtin:', 'ext:')):
                kind, nm = tgt.split(':', 1)
                g.add_node(tgt, kind=kind, name=nm)
            label = f'{c["callee"]}:{c["method"]}' if c.get('method') \
                else c['callee']
            if status == 'external':
                diag['external_calls'].append(
                    {'file': rp, 'line': c['line'], 'name': label})
            elif status == 'inferred':
                diag['inferred_calls'].append(
                    {'file': rp, 'line': c['line'], 'name': label})
            elif status == 'builtin':
                diag['builtin_calls'].append(
                    {'file': rp, 'line': c['line'], 'name': label})
            src = fid
            fn = owner(c['line'])
            if fn is not None:
                src = node_id_fn(rp, fn['name'], fn['line'])
            add_edge(src, tgt, 'CALLS', line=c['line'], status=status)

        for imp in f.get('imports') or []:
            mod = imp['module']
            hit = mod_file(mod, rp)
            if hit:
                add_edge(fid, node_id_file(hit), 'IMPORTS',
                         line=imp.get('line'), status='resolved')
            else:
                tid = 'mod:' + mod
                if not g.has_node(tid):
                    g.add_node(tid, kind='module', name=mod)
                add_edge(fid, tid, 'IMPORTS', line=imp.get('line'),
                         status='unresolved')
                diag['unresolved_imports'].append(
                    {'file': rp, 'line': imp.get('line'), 'module': mod})

        # function -> file variable READS edges
        is_py = rp.lower().endswith(('.py', '.pyi'))
        for v in f.get('file_vars') or []:
            if not (v.get('init') in ('table', 'string', 'number')
                    or v.get('value') is not None):
                continue
            vid = node_id_var(rp, v['name'], v['line'])
            for fn in fns:
                body = fn.get('body') or ''
                if body and _var_reads(body, v['name'], is_py):
                    src = node_id_fn(rp, fn['name'], fn['line'])
                    add_edge(src, vid, 'READS')

    return g, diag


def save_graph(g, path) -> str:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    data = nx.node_link_data(g, edges='edges')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    return path


def load_graph(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    return nx.node_link_graph(data, multigraph=True, edges='edges')
