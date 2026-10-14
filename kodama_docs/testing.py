"""Backend self-test harness (generic, no LLM, no markdown).

A backend bundles its own test codebase. The source of truth is what the
language actually does with it, not hand-written expectations:

* ``collect_truth()`` (backend) runs the fixture and records every call
  site and import binding the runtime resolved;
* ``parse_markers(source)`` (backend) reads the fixture's ``# expect: ...``
  lines, which pin the deliberately unresolvable cases the runtime cannot
  reach (ambiguous names, external calls, unresolved imports).

The harness is language-agnostic: it extracts the fixture with the backend's
own ``extract``, builds the kodama-docs graph (``graph.build_graph``), and
checks the graph against those two sources of truth. The graph is the
artifact under test; a failure means the translation (codebase -> graph) is
wrong, so it is reported per check and the process exits non-zero.

Protocol a backend must provide (see ``backends/python/__init__.py``):
    TEST_CODEBASE_DIR   directory holding the fixture sources
    collect_truth()     -> {'calls': [...], 'imports': [...]}
    parse_markers(s)    -> [{'line', 'kind', 'targets'}, ...]
"""
import importlib
import os
import sys

from . import graph as gmod
import backends


# ------------------------------------------------------------- plumbing

def _find_backend(name):
    for b in backends.list_backends():
        if b['name'] == name or b['dir'] == name:
            if b.get('status') != 'ready':
                issues = '; '.join(b.get('issues', [])) or 'unusable'
                raise SystemExit(f"backend {name!r} is {b.get('status')}: "
                                 f"{issues}")
            return b
    available = ', '.join(x['name'] for x in backends.list_backends()) \
        or 'none'
    raise SystemExit(f"no backend named {name!r} (installed: {available})")


def _backend_module(backend):
    try:
        return importlib.import_module(f"backends.{backend['dir']}")
    except Exception as e:  # noqa: BLE001 - report, don't crash-assert
        raise SystemExit(
            f"could not import backend {backend['name']!r}: "
            f"{type(e).__name__}: {e}")


def _fixture_files(root, exts):
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            if any(fn.endswith(e) for e in exts):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).replace(os.sep, '/')
                out.append((rel, full))
    out.sort(key=lambda x: x[0])
    return out


# ------------------------------------------------------ graph inspection

def _edge(g, u, v, etype):
    if u is None or v is None or not g.has_edge(u, v):
        return None
    for d in g.get_edge_data(u, v).values():
        if d.get('type') == etype:
            return d
    return None


def _edges_from(g, u, etype):
    out = []
    if u is None:
        return out
    for v in g.successors(u):
        for d in g.get_edge_data(u, v).values():
            if d.get('type') == etype:
                out.append((v, d))
    return out


def _owner_node(analysis, file, line):
    """The innermost function enclosing (file, line), else the file node —
    exactly the CALLS source ``graph.build_graph`` uses."""
    for r in analysis:
        if r.get('relpath') != file:
            continue
        best = None
        for fn in r.get('functions') or []:
            lo = fn['line']
            hi = fn.get('end_line', lo)
            if lo <= line <= hi:
                span = hi - lo
                if best is None or span < best[0]:
                    best = (span, fn)
        if best is not None:
            fn = best[1]
            return gmod.node_id_fn(file, fn['name'], fn['line'])
        return gmod.node_id_file(file)
    return None


def _target_node(g, relpath, name, line=None):
    """A function/class node in `relpath` named `name` (line, if given)."""
    for nid, data in g.nodes(data=True):
        if data.get('relpath') != relpath or data.get('name') != name:
            continue
        if data.get('kind') not in ('function', 'class'):
            continue
        if line is not None and data.get('line') != line:
            continue
        return nid
    return None


def _target_display(nid):
    prefix, _, rest = nid.partition(':')
    return rest if prefix in ('fn', 'var', 'cls') else nid


# ---------------------------------------------------------- truth checks

def check_truth_calls(truth, analysis, g):
    results = []
    for c in truth.get('calls') or []:
        sf, sl = c['site']['file'], c['site']['line']
        o = c['origin']
        owner = _owner_node(analysis, sf, sl)
        target = _target_node(g, o['file'], o['name'], o.get('line'))
        e = _edge(g, owner, target, 'CALLS')
        ok = bool(e and e.get('resolution_success') is True)
        if e is None:
            detail = 'no CALLS edge from the call site to the target'
        else:
            detail = (f"status={e.get('status')} "
                      f"resolution_success={e.get('resolution_success')}")
        results.append({
            'name': f"call {sf}:{sl} -> {o['file']}::{o['name']}",
            'ok': ok, 'detail': detail,
        })
    return results


def check_truth_imports(truth, analysis, g):
    results = []
    for imp in truth.get('imports') or []:
        f, line = imp['file'], imp['line']
        mf = imp.get('module_file')
        fid = gmod.node_id_file(f)
        if mf:
            tid = gmod.node_id_file(mf)
            e = _edge(g, fid, tid, 'IMPORTS')
            ok = bool(e and e.get('resolution_success') is True)
            if e is None:
                detail = f'no resolved IMPORTS edge to {mf}'
            else:
                detail = (f"status={e.get('status')} "
                          f"resolution_success={e.get('resolution_success')}")
            results.append({
                'name': f"import {f}:{line} -> {mf}",
                'ok': ok, 'detail': detail,
            })
        else:
            # stdlib / external module: must stay an *unresolved* edge,
            # never dropped and never guessed as a project file.
            bad = [(v, d) for v, d in _edges_from(g, fid, 'IMPORTS')
                   if d.get('line') == line
                   and d.get('resolution_success') is False]
            ok = len(bad) >= 1
            results.append({
                'name': f"import {f}:{line} (stdlib/external)",
                'ok': ok,
                'detail': ('unresolved IMPORTS edge present' if ok
                           else 'no unresolved IMPORTS edge on that line'),
            })
    return results


# ------------------------------------------------- soundness / meta checks
#
# The call and import checks above are *completeness* checks (the graph must
# contain what the runtime proves). These are the matching *soundness* and
# *field* checks: the graph must not contain what it shouldn't, and the
# extractor's per-function / per-variable fields must match the AST oracle.
# Without them, bugs like a phantom `from m import n` or a dropped `*args`
# were invisible, because they emit *extra* records / wrong field values
# rather than missing edges.

def _analysis_by_file(analysis):
    out = {}
    for a in analysis:
        out[a['relpath']] = a
    return out


def check_import_soundness(truth, analysis):
    """Per (file, line): the extractor must emit exactly as many import
    records as the runtime imported. A phantom `from m import n` that also
    emits an import for `m` (one too many) or a dropped name (one too few)
    fails here — invisible to the completeness-only import check above."""
    by_file = _analysis_by_file(analysis)
    truth_counts = {}
    for imp in truth.get('imports') or []:
        key = (imp['file'], imp['line'])
        truth_counts[key] = truth_counts.get(key, 0) + 1
    extract_counts = {}
    for rel, a in by_file.items():
        for rec in a.get('imports') or []:
            key = (rel, rec.get('line'))
            extract_counts[key] = extract_counts.get(key, 0) + 1
    results = []
    for key in sorted(truth_counts):
        f, line = key
        n_truth = truth_counts[key]
        n_extract = extract_counts.get(key, 0)
        ok = (n_truth == n_extract)
        results.append({
            'name': f'import-count {f}:{line}',
            'ok': ok,
            'detail': (f'runtime={n_truth} extracted={n_extract}'
                       + ('' if ok else '  <-- phantom/missing import')),
        })
    return results


def check_function_meta(truth, analysis):
    """Per function the AST oracle recorded: the extractor's params (order +
    names, incl. *args/**kwargs), vararg flag, and qualified name (methods as
    ``Class.method``) must match. Guards the *args/**kwargs drop, the
    `size=1024*1024` vararg false positive, and the method-qualification gap."""
    by_file = _analysis_by_file(analysis)
    results = []
    for meta in truth.get('modules') or []:
        f = meta['file']
        a = by_file.get(f)
        if a is None:
            continue
        # key by (name, line): a name like __init__ recurs across a class
        # hierarchy, so name alone is not a unique identity.
        fns = {(fn['name'], fn.get('line')): fn for fn in a.get('functions') or []}
        for t in meta.get('functions') or []:
            name = t['name']
            got = fns.get((name, t['line']))
            if got is None:
                results.append({
                    'name': f'function {f}::{name}',
                    'ok': False,
                    'detail': 'function not extracted',
                })
                continue
            probs = []
            if got.get('params') != t['params']:
                probs.append(f"params {got.get('params')} != {t['params']}")
            if bool(got.get('vararg')) != bool(t['vararg']):
                probs.append(f"vararg {got.get('vararg')} != {t['vararg']}")
            if got.get('qualified') != t['qualified']:
                probs.append(
                    f"qualified {got.get('qualified')!r} != {t['qualified']!r}")
            if t.get('has_comment'):
                if not got.get('developer_comment'):
                    probs.append(
                        'developer_comment missing (line above def is a comment)')
            results.append({
                'name': f'function {f}::{name}',
                'ok': not probs,
                'detail': ('; '.join(probs) if probs
                           else f"{name}({', '.join(t['params'])})"
                              + (' *' if t['vararg'] else '')
                              + f" -> {t['qualified']}"),
            })
    return results


def check_file_vars(truth, analysis):
    """Module-level variables must be extracted as file_vars; class
    attributes must NOT leak out as file_vars. Guards the `class A: X=1`
    leak (a class attr recorded as a module variable)."""
    by_file = _analysis_by_file(analysis)
    results = []
    for meta in truth.get('modules') or []:
        f = meta['file']
        a = by_file.get(f)
        if a is None:
            continue
        got_vars = {v['name'] for v in a.get('file_vars') or []}
        expected = {v['name'] for v in meta.get('file_vars') or []}
        forbidden = {c['name'] for c in meta.get('class_attrs') or []}
        missing = expected - got_vars
        leaked = forbidden & got_vars
        ok = (not missing) and (not leaked)
        detail = (f"vars {sorted(expected)}"
                  + (f"  missing={sorted(missing)}" if missing else '')
                  + (f"  leaked-class-attrs={sorted(leaked)}" if leaked else ''))
        results.append({'name': f'file-vars {f}', 'ok': ok, 'detail': detail})
    return results


# -------------------------------------------------------- marker checks

def _diag_lines(diag, key):
    return {(d.get('file'), d.get('line')) for d in diag.get(key, [])}


def _node_name_at(g, nid):
    d = g.nodes.get(nid) or {}
    return d.get('name')


def _matches_target(g, nid, file, name):
    if nid is None:
        return False
    d = g.nodes.get(nid) or {}
    return d.get('relpath') == file and d.get('name') == name


def check_markers(markers_by_file, analysis, g, diag):
    results = []
    for file in sorted(markers_by_file):
        for m in markers_by_file[file]:
            line, kind, targets = m['line'], m['kind'], m['targets']
            label = f"{kind} {file}:{line}" + (
                f" ({targets[0]})" if targets else '')
            ok, detail = _check_one_marker(
                kind, file, line, targets, analysis, g, diag)
            results.append({'name': label, 'ok': ok, 'detail': detail})
    return results


def _check_one_marker(kind, file, line, targets, analysis, g, diag):
    if kind == 'ambiguous':
        hit = (file, line) in _diag_lines(diag, 'ambiguous_calls')
        return (hit, 'recorded as ambiguous (no edge, candidates shown)'
                if hit else 'not in ambiguous_calls')

    if kind == 'import-unresolved':
        hit = (file, line) in _diag_lines(diag, 'unresolved_imports')
        return (hit, 'recorded as an unresolved import' if hit
                else 'not in unresolved_imports')

    if kind in ('external', 'builtin'):
        key = 'external_calls' if kind == 'external' else 'builtin_calls'
        hit = (file, line) in _diag_lines(diag, key)
        return (hit, f'recorded in {key}' if hit
                else f'not in {key}')

    if kind == 'import':
        # `import <file>`: a resolved IMPORTS edge to that project file.
        mf = targets[0] if targets else None
        if not mf:
            return (False, 'marker needs a target file')
        e = _edge(g, gmod.node_id_file(file), gmod.node_id_file(mf),
                  'IMPORTS')
        ok = bool(e and e.get('resolution_success') is True)
        return (ok, 'resolved IMPORTS edge present' if ok
                else f'no resolved IMPORTS edge to {mf}')

    # resolved / inferred: a CALLS edge to the named symbol with the
    # expected status (never the other, and never ambiguous/external).
    if kind in ('resolved', 'inferred'):
        tgt = targets[0] if targets else None
        if not tgt or '::' not in tgt:
            return (False, f'marker needs a <file>::<name> target '
                           f'(got {tgt!r})')
        tfile, tname = tgt.split('::', 1)
        owner = _owner_node(analysis, file, line)
        # find the CALLS edge(s) on this line leaving the owner
        hits = [(v, d) for v, d in _edges_from(g, owner, 'CALLS')
                if d.get('line') == line]
        # the one whose target is the expected symbol
        good = [e for v, e in hits
                if _matches_target(g, v, tfile, tname)]
        if not good:
            # maybe no edge at all (ambiguous) or wrong target
            names = sorted(_node_name_at(g, v) or v for v, _d in hits)
            return (False, f'no {kind} edge to {tfile}::{tname}'
                           + (f' (edges to: {names})' if names
                              else ' (no CALLS edge on this line)'))
        e = good[0]
        status_ok = e.get('status') == kind
        rs_ok = e.get('resolution_success') is True
        ok = status_ok and rs_ok
        detail = (f"status={e.get('status')} "
                  f"resolution_success={e.get('resolution_success')} "
                  f"(expected {kind})")
        return (ok, detail)

    return (False, f'unknown marker kind {kind!r}')


# ---------------------------------------------------------- orchestration

def test_backend(name):
    """Run one backend's self-test. Returns the exit code (0 pass /
    1 fail / 2 the backend has no test codebase)."""
    backend = _find_backend(name)
    mod = _backend_module(backend)

    missing = [a for a in ('TEST_CODEBASE_DIR', 'collect_truth',
                           'parse_markers') if not hasattr(mod, a)]
    if missing:
        print(f"backend {backend['name']!r} does not implement the "
              f"self-test protocol (missing: {', '.join(missing)})")
        return 2

    root = os.path.abspath(str(mod.TEST_CODEBASE_DIR))
    if not os.path.isdir(root):
        print(f"test codebase directory not found: {root}")
        return 2

    exts = [e.lower() for e in backend.get('extensions', [])] or ['']
    fixture = _fixture_files(root, exts)
    if not fixture:
        print(f'no fixture sources found under {root}')
        return 2

    # 1) ground truth from the language runtime
    print(f"backend:    {backend['name']} ({backend['dir']})")
    print(f"fixture:    {root}  ({len(fixture)} files)")
    print('running fixture to collect runtime truth ...')
    try:
        truth = mod.collect_truth()
    except Exception as e:  # noqa: BLE001 - a broken fixture must fail loudly
        print(f'  truth generation FAILED: {e}')
        return 1
    n_truth_calls = len(truth.get('calls') or [])
    n_truth_imports = len(truth.get('imports') or [])
    print(f'  truth: {n_truth_calls} call sites, '
          f'{n_truth_imports} import bindings')

    # 2) extract the fixture with this backend's own translator
    analysis, extract_failures = [], []
    for rel, full in fixture:
        try:
            with open(full, 'r', encoding='utf-8', errors='replace') as fh:
                src = fh.read()
        except OSError as e:
            extract_failures.append((rel, f'read: {e}'))
            continue
        try:
            r = backends.extract(src, rel)
        except Exception as e:  # noqa: BLE001 - per-file isolation by design
            extract_failures.append(
                (rel, f'{type(e).__name__}: {e}'))
            continue
        r['relpath'] = rel
        r['lines'] = len(src.splitlines())
        r['status'] = 'ok'
        analysis.append(r)

    if extract_failures:
        print(f'  extraction FAILED for {len(extract_failures)} file(s):')
        for rel, err in extract_failures:
            print(f'    {rel}: {err}')

    # 3) build the kodama-docs graph (the artifact under test)
    g, diag = gmod.build_graph(analysis)

    # 4) markers: the backend parses its own comment convention
    markers_by_file = {}
    for r in analysis:
        rel = r['relpath']
        full = os.path.join(root, rel)
        try:
            with open(full, 'r', encoding='utf-8', errors='replace') as fh:
                src = fh.read()
        except OSError:
            continue
        for m in mod.parse_markers(src):
            markers_by_file.setdefault(rel, []).append(m)
    n_markers = sum(len(v) for v in markers_by_file.values())

    # 5) checks
    results = []
    results += [('truth-call', c) for c in
                check_truth_calls(truth, analysis, g)]
    results += [('truth-import', c) for c in
                check_truth_imports(truth, analysis, g)]
    # soundness + field checks (only when the truth supplies the extra module
    # meta; a backend whose truth omits it is skipped, not failed)
    if truth.get('modules'):
        results += [('soundness-import', c) for c in
                    check_import_soundness(truth, analysis)]
        results += [('meta-function', c) for c in
                    check_function_meta(truth, analysis)]
        results += [('meta-filevars', c) for c in
                    check_file_vars(truth, analysis)]
    results += [('marker', c) for c in
                check_markers(markers_by_file, analysis, g, diag)]

    passed = sum(1 for _tag, c in results if c['ok'])
    failed = sum(1 for _tag, c in results if not c['ok'])

    print(f"  graph: {len(g.nodes)} nodes, {len(g.edges)} edges, "
          f"{n_markers} markers")
    print()
    print(f"{'CHECK':<6} {'ok':<4} {'detail':<42} check")
    print('-' * 96)
    for _tag, c in results:
        mark = 'PASS' if c['ok'] else 'FAIL'
        print(f"{mark:<6} {'yes' if c['ok'] else 'no':<4} "
              f"{c['detail'][:42]:<42} {c['name']}")

    print()
    print(f"RESULT: {passed}/{len(results)} passed, {failed} failed")
    if failed:
        print('\nFailed checks:')
        for _tag, c in results:
            if not c['ok']:
                print(f"  FAIL  {c['name']}: {c['detail']}")
        return 1
    return 0
