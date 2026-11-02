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


def _var_reads(body: str, name: str, is_py: bool, params=()) -> bool:
    """True if `body` references file variable `name`.

    A reference is an identifier use. A reference is not counted when the
    function shadows the name itself — its own parameter, its own name, or
    a local declared/assigned in its body.
    """
    if name in (params or ()):
        return False
    e = re.escape(name)
    if not re.search(r'(?<![\w.])' + e + r'(?!\w)', body):
        return False
    if is_py:
        shadowed = re.search(r'(?m)^\s*' + e + r'\s*=[^=]', body) \
            or re.search(r'\b' + e + r'\s*[-+*/%&|^]=', body) \
            or re.search(r'\bfor\s+[^\n:]*\b' + e + r'\b[^\n]*\bin\b', body) \
            or re.search(r'\bas\s+' + e + r'\b', body) \
            or re.search(r'\b' + e + r'\s*:=', body)
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


def _edge_attrs(g, u, v):
    return (g.get_edge_data(u, v) or {}).values()


def graph_neighbor_names(g, node_id):
    """(called_by, calls) name lists from a node's CALLS edges.

    Used both for the LLM context ("Called by:" / "Calls:") and for the
    record fingerprint, so cached prose is invalidated when the
    call-relationship set of a symbol changes. O(in+out degree) instead of
    scanning every edge in the graph."""
    ins, outs = [], []
    if not g.has_node(node_id):
        return ins, outs
    for u in g.predecessors(node_id):
        for data in _edge_attrs(g, u, node_id):
            if data.get('type') == 'CALLS':
                nm = g.nodes[u].get('name')
                if nm:
                    ins.append(nm)
                break
    for v in g.successors(node_id):
        for data in _edge_attrs(g, node_id, v):
            if data.get('type') == 'CALLS':
                nm = g.nodes[v].get('name') if g.has_node(v) else None
                if nm:
                    outs.append(nm)
                break
    return ins, outs


def graph_read_names(g, node_id):
    """File-level variable names a function reads (READS edges)."""
    out = []
    if not g.has_node(node_id):
        return out
    for v in g.successors(node_id):
        for data in _edge_attrs(g, node_id, v):
            if data.get('type') == 'READS':
                nm = g.nodes[v].get('name') if g.has_node(v) else None
                if nm:
                    out.append(nm)
                break
    return list(dict.fromkeys(out))


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


def _is_plain_def(fn) -> bool:
    """True for a function that is callable by its bare name.

    Methods / table functions (``Class.method``, ``M.helper``) are only
    reachable through their receiver, so they must not participate in
    bare-name lookup or bare-name inference. Nested functions inside a
    method are still plain: they are local to that method.
    """
    return (fn.get('qualified') or fn['name']) == fn['name']


def _is_direct_method(fn, fns, classes) -> bool:
    """Direct member of a class/table (not a nested function inside one)."""
    in_class = any(c['line'] < fn['line'] <= c.get('end_line', c['line'])
                   for c in classes)
    if not classes:
        # Lua has no class records: a qualified name is the table receiver
        # (`M.helper`); a nested local function stays plain (`helper`).
        return (fn.get('qualified') or fn['name']) != fn['name']
    if not in_class:
        return False
    return not any(g is not fn and g['line'] < fn['line']
                   <= g.get('end_line', g['line']) for g in fns)


def _resolve_in_scope(fn_list, name, line, plain_ids=None):
    """The definition of ``name`` visible at ``line`` (Python scoping).

    Walks out from the innermost function enclosing the call to the module;
    in each scope the most recent definition of ``name`` before the call
    wins, so a redefinition shadows the earlier one from that point on.
    Only plain (non-method) definitions are considered. ``plain_ids`` is
    the set of ``id(fn)`` values that are bare-callable; when omitted the
    qualified-name heuristic is used."""
    def is_plain(f):
        if plain_ids is not None:
            return id(f) in plain_ids
        return _is_plain_def(f)

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
                 if is_plain(f) and f['name'] == name
                 and _parent_of(f, fn_list) is scope
                 and f['line'] < line]
        if cands:
            return cands[-1]
        scope = _parent_of(scope, fn_list)

    cands = [f for f in fn_list
             if is_plain(f) and f['name'] == name
             and _parent_of(f, fn_list) is None
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
    qual_cands = {}    # qualified name -> [fn ids]
    name_cands = {}    # plain name     -> [fn/class ids] (method inference)
    top_name_cands = {}  # plain name  -> [module-level fn/class ids]
    file_fn = {}       # (relpath, plain name) -> module-level fn id
    file_fn_q = {}     # (relpath, qualified)  -> fn id
    file_named = {}    # (relpath, plain name) -> [all fn ids with that name]
    file_cls = {}      # (relpath, class name) -> class node id
    plain_ids = set()  # id(fn) for functions callable by their bare name
    for f in files:
        rp = f['relpath']
        fid = node_id_file(rp)
        classes_all = f.get('classes') or []
        fns_all = f.get('functions') or []
        g.add_node(fid, kind='file', relpath=rp,
                   lines=f.get('lines'),
                   function_count=len(fns_all),
                   variable_count=len(f.get('file_vars') or []))
        for c in classes_all:
            cid = node_id_cls(rp, c['name'], c['line'])
            g.add_node(cid, kind='class', relpath=rp, name=c['name'],
                       qualified=c.get('qualified') or c['name'],
                       line=c['line'],
                       end_line=c.get('end_line', c['line']), file_id=fid)
            add_edge(fid, cid, 'CONTAINS')
            if (c.get('qualified') or c['name']) == c['name']:
                file_cls[(rp, c['name'])] = cid
                top_name_cands.setdefault(c['name'], []).append(cid)
            name_cands.setdefault(c['name'], []).append(cid)
        for fn in fns_all:
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
            file_fn_q[(rp, qual)] = nid
            file_named.setdefault((rp, fn['name']), []).append(nid)
            if not _is_direct_method(fn, fns_all, classes_all):
                plain_ids.add(id(fn))
                file_fn[(rp, fn['name'])] = nid
                top_name_cands.setdefault(fn['name'], []).append(nid)
        for v in f.get('file_vars') or []:
            vid = node_id_var(rp, v['name'], v['line'])
            g.add_node(vid, kind='variable', relpath=rp, name=v['name'],
                       line=v['line'], init=v.get('init', 'expr'),
                       file_id=fid)
            add_edge(fid, vid, 'CONTAINS')
    for ids in (list(qual_cands.values()) + list(name_cands.values())
                + list(top_name_cands.values())
                + list(file_named.values())):
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

    def resolve(rp, name, method, line, owner_fn=None):
        """Resolve one call site using the context of file `rp`.

        Returns (target_node_id, status) or None when the candidates are
        ambiguous (the call site is recorded in diag; no edge is written).

        ``owner_fn`` is the innermost function enclosing the call; it is
        what lets ``self.method()`` / ``cls.method()`` resolve inside the
        right class instead of being mistaken for a builtin.
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

        def one_or_ambiguous(cands):
            cands = dedup(cands)
            if not cands:
                return None
            return (cands[0], 'resolved') if len(cands) == 1 \
                else ambiguous(cands)

        def owner_class():
            q = (owner_fn or {}).get('qualified') or (owner_fn or {}).get('name')
            return q.rsplit('.', 1)[0] if q and '.' in q else None

        def file_named_hits(bf, plain):
            """All functions in file ``bf`` with plain name ``plain``.
            Top-level functions win; methods/table functions are only used
            when there is no module-level candidate."""
            top = file_fn.get((bf, plain))
            return [top] if top else list(file_named.get((bf, plain), []))

        if method and name:
            # 0) self/cls: the enclosing class is known statically. Resolve
            #    `Class.method` directly; never classify self/cls as a
            #    builtin (they are not callables).
            if name in ('self', 'cls'):
                cls = owner_class()
                if cls:
                    cands = qual_cands.get(f'{cls}.{method}')
                    if cands:
                        return one_or_ambiguous(cands)

            # 1) dotted receiver that is a project MODULE path
            #    (e.g. `deep.pack.mod.launch(...)`): resolve the module to
            #    its file, then the method within that file
            if '.' in name:
                mf = mod_file(name, rp)
                if mf:
                    hit = (file_fn_q.get((mf, f'{name}.{method}'))
                           or file_fn.get((mf, method))
                           or file_cls.get((mf, method)))
                    if hit:
                        return hit, 'resolved'
                    hits = file_named_hits(mf, method)
                    if hits:
                        return one_or_ambiguous(hits)

            # 2) object bound to a project module in this file -> its method
            hits = []
            for b in file_bs:
                if b['bind'] != name or not b['file']:
                    continue
                bf, target = b['file'], b.get('name')
                if target:
                    hit = file_fn_q.get((bf, f'{target}.{method}'))
                    if hit:
                        hits.append(hit)
                        continue
                hit = (file_fn.get((bf, method))
                       or file_cls.get((bf, method)))
                if hit:
                    hits.append(hit)
                else:
                    hits.extend(file_named_hits(bf, method))
            if hits:
                return one_or_ambiguous(hits)

            # 3) exact qualified name `name.method` defined in the project
            #    (covers `V.add`, `Body.reset`, Lua `M.helper`, ...)
            cands = qual_cands.get(f'{name}.{method}')
            if cands:
                return one_or_ambiguous(cands)

            # 4) object (or its root) is a stdlib/builtin name — never
            #    guess a project function with the same method name.
            #    self/cls are deliberately excluded (see step 0).
            if name not in ('self', 'cls') and (
                    name in builtins or name.split('.', 1)[0] in builtins):
                return 'builtin:' + label, 'builtin'

            # 5) method name unique project-wide (unbound object, e.g. a
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
                if b['bind'] != base or not b['file']:
                    continue
                bf, target = b['file'], b.get('name')
                if target:
                    hit = file_fn_q.get((bf, f'{target}.{rest}'))
                    if hit:
                        hits.append(hit)
                        continue
                hits.extend(file_named_hits(bf, rest))
            if hits:
                return one_or_ambiguous(hits)
            # 2) exact qualified name in the project (`M.helper`, `V.add`)
            cands = qual_cands.get(name)
            if cands:
                return one_or_ambiguous(cands)
            # 3) builtin namespace (math.sqrt, io.open, os.path.join, ...)
            if base in builtins:
                return 'builtin:' + name, 'builtin'
            return 'ext:' + name, 'external'

        # bare name
        # 1) defined in the same file — scope-aware: the definition visible
        #    at the call line wins (a nested def shadows the module level,
        #    and a redefinition shadows the earlier one from that point on).
        #    Only plain functions/classes participate; methods are not
        #    callable bare.
        fentry = files_by_rp.get(rp)
        if fentry is not None:
            fn = _resolve_in_scope(fentry.get('functions') or [], name, line,
                                   plain_ids=plain_ids)
            if fn is not None:
                return node_id_fn(rp, fn['name'], fn['line']), 'resolved'
            cands = [c for c in (fentry.get('classes') or [])
                     if (c.get('qualified') or c['name']) == c['name']
                     and c['name'] == name and c['line'] < line]
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
            return one_or_ambiguous(hits)
        # 3) builtin
        if name in builtins:
            return 'builtin:' + name, 'builtin'
        # 4) module-level name unique project-wide — documented inference
        cands = top_name_cands.get(name)
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
            fn = owner(c['line'])
            res = resolve(rp, c['callee'], c.get('method'), c['line'],
                          owner_fn=fn)
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
            if v.get('module'):
                # module aliases are represented by IMPORTS, not READS
                continue
            if not (v.get('init') in ('table', 'string', 'number')
                    or v.get('value') is not None):
                continue
            vid = node_id_var(rp, v['name'], v['line'])
            for fn in fns:
                body = fn.get('body') or ''
                if v['name'] == fn['name']:
                    continue
                if body and _var_reads(body, v['name'], is_py,
                                       fn.get('params') or ()):
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


#: Node attributes only useful to the analysis pipeline, not to the graph
#: viewer. The full graph keeps them (it is the reusable artifact); the
#: "diet" graph used by /api/graph and the static site drops them.
_DIET_NODE_DROP = {'body', 'params', 'vararg', 'end_line', 'file_id'}


def diet_graph_data(g) -> dict:
    """node-link data for serving: same relationships, no source bodies.

    The full graph remains complete on disk (``graph.json``). This is only
    what a browser needs to draw it, so large function bodies are not sent
    over the wire or inlined into the static site."""
    data = nx.node_link_data(g, edges='edges')
    for node in data.get('nodes', []):
        for key in _DIET_NODE_DROP:
            node.pop(key, None)
    return data


def save_diet_graph(g, path) -> str:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(diet_graph_data(g), fh, ensure_ascii=False, indent=1)
    return path


def load_graph(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    return nx.node_link_graph(data, multigraph=True, edges='edges')
