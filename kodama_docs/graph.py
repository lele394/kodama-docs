"""Deterministic cross-file graph builder (networkx MultiDiGraph).

Node kinds: file, function, variable, class, builtin, external, module.
Edge kinds: CONTAINS (file -> fn/var/cls), CALLS (fn/file -> fn/cls/ext/builtin),
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

Every reference edge (CALLS / IMPORTS / READS) also carries
``resolution_success`` (boolean): true when the reference was matched to a
known symbol (a project function/class/variable, or a recognized builtin);
false when it stays external or unresolved. Renderers use it to highlight
unresolved references (orange) instead of guessing.

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


def node_id_cls(relpath, name, line):
    return f'cls:{relpath}::{name}@{line}'


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
    """Human-readable candidate form: 'fn:a.py::b@3' / 'cls:a.py::B@2'
    -> 'a.py::b@3' / 'a.py::B@2'."""
    prefix, _, rest = nid.partition(':')
    if prefix in ('fn', 'var', 'cls'):
        return rest
    return nid


def _parent_of(f, fn_list):
    """Innermost function that strictly contains ``f``'s def line, or None.

    Two defs at the same depth never contain each other, so the innermost
    container is unambiguously the one whose body ends earliest."""
    best = None
    for g in fn_list:
        if g is f:
            continue
        if g['line'] < f['line'] and f['line'] <= g.get('end_line', g['line']):
            if best is None or g.get('end_line', g['line']) < best.get('end_line', best['line']):
                best = g
    return best


def _resolve_in_scope(fn_list, name, line):
    """The definition of ``name`` visible at ``line`` (Python scoping).

    Walks out from the innermost function enclosing the call to the module;
    in each scope the most recent definition of ``name`` before the call
    wins, so a redefinition shadows the earlier one from that point on."""
    def encloses(f, L):
        return f['line'] <= L <= f.get('end_line', f['line'])

    def depth(f):
        d = 0
        for g in fn_list:
            if g is not f and g['line'] < f['line'] and f['line'] <= g.get('end_line', g['line']):
                d += 1
        return d

    inner, best_depth = None, -1
    for f in fn_list:
        if encloses(f, line):
            d = depth(f)
            if d > best_depth:
                inner, best_depth = f, d

    scope = inner
    while scope is not None:
        cands = [f for f in fn_list
                 if f['name'] == name and _parent_of(f, fn_list) is scope
                 and f['line'] < line]
        if cands:
            return cands[-1]
        scope = _parent_of(scope, fn_list)

    cands = [f for f in fn_list
             if f['name'] == name and _parent_of(f, fn_list) is None
             and f['line'] < line]
    return cands[-1] if cands else None


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
    file_cls = {}    # (relpath, class name) -> class node id
    for f in files:
        rp = f['relpath']
        fid = node_id_file(rp)
        g.add_node(fid, kind='file', relpath=rp,
                   lines=f.get('lines'),
                   function_count=len(f.get('functions') or []),
                   variable_count=len(f.get('file_vars') or []))
        for c in f.get('classes') or []:
            cid = node_id_cls(rp, c['name'], c['line'])
            g.add_node(cid, kind='class', relpath=rp, name=c['name'],
                       qualified=c.get('qualified') or c['name'],
                       line=c['line'],
                       end_line=c.get('end_line', c['line']), file_id=fid)
            add_edge(fid, cid, 'CONTAINS')
            if (rp, c['name']) not in file_cls:
                file_cls[(rp, c['name'])] = cid
            name_cands.setdefault(c['name'], []).append(cid)
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
    files_by_rp = {f['relpath']: f for f in files}

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
        if name is None:
            # The callee is computed at runtime (`open(..).read()`,
            # `cfg['k'].update(..)`, `getattr(..)(..)`): no static target
            # exists, so the call stays VISIBLE as an external reference
            # (`?.method` / `?`) rather than being silently dropped.
            label = f'?.{method}' if method else '?'
            return 'ext:' + label, 'external'
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
            # 0) dotted receiver that is a project MODULE path
            #    (e.g. `deep.pack.mod.launch(...)`): resolve the module to
            #    its file, then the method within that file
            if '.' in name:
                mf = mod_file(name, rp)
                if mf:
                    hit = (file_fn.get((mf, method))
                           or file_cls.get((mf, method)))
                    if hit:
                        return hit, 'resolved'
            # 1) object bound to a project module in this file -> its method
            hits = []
            for b in file_bs:
                if b['bind'] == name and b['file']:
                    hit = (file_fn.get((b['file'], method))
                           or file_cls.get((b['file'], method)))
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
                    hit = (file_fn.get((b['file'], b['name'] or rest))
                           or file_cls.get((b['file'], b['name'] or rest)))
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
        # 1) defined in the same file — scope-aware: the definition visible
        #    at the call line wins (a nested def shadows the module level,
        #    and a redefinition shadows the earlier one from that point on)
        fentry = files_by_rp.get(rp)
        if fentry is not None:
            fn = _resolve_in_scope(fentry.get('functions') or [], name, line)
            if fn is not None:
                return node_id_fn(rp, fn['name'], fn['line']), 'resolved'
            cands = [c for c in (fentry.get('classes') or [])
                     if c['name'] == name and c['line'] < line]
            if cands:
                c = cands[-1]
                return node_id_cls(rp, c['name'], c['line']), 'resolved'
        # 2) bound by this file's imports to a project file
        #    (`from users import validate` then `validate()`, or
        #    `from physics.body import Body` then `Body(...)`)
        hits = []
        for b in file_bs:
            if b['bind'] == name and b['file'] and b['name']:
                hit = (file_fn.get((b['file'], b['name']))
                       or file_cls.get((b['file'], b['name'])))
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
            callee, mth = c.get('callee'), c.get('method')
            if callee is None:
                label = f'?.{mth}' if mth else '?'
            elif mth:
                label = f'{callee}.{mth}'
            else:
                label = callee
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
            add_edge(src, tgt, 'CALLS', line=c['line'], status=status,
                     resolution_success=status in ('resolved', 'inferred',
                                                    'builtin'))

        for imp in f.get('imports') or []:
            mod = imp['module']
            hit = mod_file(mod, rp)
            if hit:
                add_edge(fid, node_id_file(hit), 'IMPORTS',
                         line=imp.get('line'), status='resolved',
                         resolution_success=True)
            else:
                tid = 'mod:' + mod
                if not g.has_node(tid):
                    g.add_node(tid, kind='module', name=mod)
                add_edge(fid, tid, 'IMPORTS', line=imp.get('line'),
                         status='unresolved', resolution_success=False)
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
                    # A READS edge only exists when the variable is defined
                    # in the same file, so it is always resolved.
                    add_edge(src, vid, 'READS', resolution_success=True)

    return g, diag


def resolution_summary(g) -> dict:
    """Aggregate the ``resolution_success`` flag across reference edges.

    Returns ``{'calls': {...}, 'imports': {...}, 'reads': {...}}`` where each
    has ``success`` / ``failed`` edge counts. ``failed`` means the reference
    did not resolve (external call, unresolved import) — exactly the
    references the renderers highlight in orange."""
    ok = {'CALLS': 0, 'IMPORTS': 0, 'READS': 0}
    fail = {'CALLS': 0, 'IMPORTS': 0, 'READS': 0}
    for _u, _v, d in g.edges(data=True):
        et = d.get('type')
        if et not in ok:
            continue
        if d.get('resolution_success'):
            ok[et] += 1
        else:
            fail[et] += 1
    return {'calls': {'success': ok['CALLS'], 'failed': fail['CALLS']},
            'imports': {'success': ok['IMPORTS'], 'failed': fail['IMPORTS']},
            'reads': {'success': ok['READS'], 'failed': fail['READS']}}


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
