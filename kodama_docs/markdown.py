"""Deterministic markdown output: anchors, links, call graphs, per-file
pages and the index. No LLM prose except the record strings passed in.
"""
import os
from urllib.parse import quote

from kodama_docs.graph import node_id_fn
from kodama_docs.util import fence_lang, sanitize_id, trunc


def enc_path(path: str) -> str:
    """Percent-encode a relative markdown link target for the static output
    (spaces -> ``%20``), keeping ``/`` path separators intact. The web server
    ``unquote``s the URL on the way in, so encoded links resolve to the
    on-disk files; raw spaces in a written ``.md`` link would not."""
    return quote(path, safe='/')


def md_escape(s: str) -> str:
    return str(s).replace('|', '\\|')


def _html_escape(s: str) -> str:
    return (str(s).replace('&', '&amp;')
            .replace('<', '&lt;').replace('>', '&gt;'))


# Unresolved references (resolution_success == false) are highlighted with
# this color so the user can spot them at a glance (orange, per request).
UNRESOLVED_COLOR = '#e67e22'


def _unresolved_span(name: str) -> str:
    """Orange inline-HTML span marking a reference that did not resolve."""
    return (f'<span style="color:{UNRESOLVED_COLOR}">'
            f'{_html_escape(name)}</span>')


def _fn_anchor(fn: dict) -> str:
    return f"fn-{sanitize_id(fn['name'])}-{fn['line']}"


def _rel_link(from_rel: str, to_rel: str) -> str:
    """Relative markdown link from files/<from_rel>.md to files/<to_rel>.md."""
    p = os.path.relpath(to_rel + '.md', os.path.dirname(from_rel) or '.')
    return enc_path(p.replace(os.sep, '/'))


def build_call_indexes(g):
    """One O(E) pass over the graph, used at render time instead of a full
    edge scan per function (O(F×E) on a big corpus):

    - ``out[u] = [(v, line, status), ...]`` — CALLS and READS edges
      leaving u (the function's deterministic references; status is
      resolved/inferred/builtin/external for CALLS, None for READS);
    - ``in[v]  = [(u, line), ...]`` — CALLS edges entering v
      (the function's call sites).
    """
    out, inc = {}, {}
    if g is None:
        return out, inc
    for u, v, d in g.edges(data=True):
        t = d.get('type')
        if t == 'CALLS':
            out.setdefault(u, []).append(
                (v, d.get('line'), d.get('status')))
            inc.setdefault(v, []).append((u, d.get('line')))
        elif t == 'READS':
            out.setdefault(u, []).append((v, d.get('line'), None))
    return out, inc


def callers_of(g, fn_id: str, call_in=None):
    """Deterministic list of call sites targeting a function node.

    Each item is a dict: file (caller relpath), name/qualified/line (the
    calling function; all None when the call happens at file level) and
    call (the call-site line). Sorted by (file, call, name).

    With a prebuilt ``call_in`` index (from :func:`build_call_indexes`) this
    is an O(in-degree) lookup; without one it builds the index on the fly.
    """
    if call_in is None:
        _, call_in = build_call_indexes(g)
    out = []
    for u, line in call_in.get(fn_id, ()):
        s = g.nodes[u]
        if s.get('kind') == 'function':
            out.append({'file': s.get('relpath') or '',
                        'name': s.get('name') or '',
                        'qualified': s.get('qualified') or s.get('name') or '',
                        'line': s.get('line'),
                        'call': line})
        else:
            out.append({'file': s.get('relpath') or '',
                        'name': None, 'qualified': None, 'line': None,
                        'call': line})
    out.sort(key=lambda c: (c['file'], c['call'] or 0, c['name'] or ''))
    return out


def callgraph_section(rel: str, fn: dict, g, call_in=None) -> list:
    """Markdown lines for the deterministic Call graph section (or [])."""
    sites = callers_of(g, node_id_fn(rel, fn['name'], fn['line']), call_in)
    if not sites:
        return []
    lines = ['**Call graph**', '']
    by_file = {}
    for s in sites:
        by_file.setdefault(s['file'], []).append(s)
    for cfile in sorted(by_file):
        file_link = _rel_link(rel, cfile)
        lines.append(f'- [{cfile}]({file_link})')
        for s in by_file[cfile]:
            link = file_link
            if s['name']:
                label = f"{s['qualified'] or s['name']}:{s['call']}"
                link += '#fn-' + sanitize_id(s['name']) + '-' + str(s['line'])
            else:
                label = f'top-level:{s["call"]}'
            lines.append(f'  - [{label}]({link})')
    lines.append('')
    return lines


def symbol_index(g):
    """Deterministic link targets for References bullets: file relpaths,
    function nodes by name / qualified name, and module namespaces
    (qualified-name prefixes) -> the file(s) they live in (from the graph)."""
    files, by_name, by_qname, by_ns, by_var = set(), {}, {}, {}, {}
    if g is None:
        return files, by_name, by_qname, by_ns, by_var
    for nid, nd in g.nodes(data=True):
        kind = nd.get('kind')
        if kind not in ('function', 'variable', 'class'):
            continue
        rp = nd.get('relpath')
        if rp:
            files.add(rp)
        nm = nd.get('name')
        if kind == 'variable':
            if nm and rp:
                by_var.setdefault(nm, set()).add(rp)
            continue
        if nm:
            by_name.setdefault(nm, []).append(nd)
        qn = nd.get('qualified') or nm
        if qn:
            by_qname.setdefault(qn, []).append(nd)
            if rp:
                parts = qn.split('.')
                for i in range(1, len(parts)):
                    by_ns.setdefault('.'.join(parts[:i]), set()).add(rp)
    return files, by_name, by_qname, by_ns, by_var


def _pick_node(cands, rel):
    """Deterministic choice among matching nodes: the current file wins,
    then a unique match; anything ambiguous stays unlinked."""
    if len(cands) == 1:
        return cands[0]
    cur = [n for n in cands if n.get('relpath') == rel]
    return cur[0] if len(cur) == 1 else None


def ref_line(rel, ref, files, by_name, by_qname, by_ns, by_var):
    """Markdown bullet for a References entry. Linked when the entry names
    a known file, function, module namespace, or file-level variable;
    plain text otherwise (e.g. builtins)."""
    text = str(ref).strip()
    t = text[:-2].strip() if text.endswith('()') else text
    ft = t.replace('\\', '/')
    while ft.startswith('./'):
        ft = ft[2:]
    if ft in files:
        return f'- [{md_escape(ref)}]({_rel_link(rel, ft)})'
    cands = []
    for mapping in (by_name, by_qname):
        for n in mapping.get(t) or []:
            if all(n is not x for x in cands):
                cands.append(n)
    node = _pick_node(cands, rel) if cands else None
    if node is not None:
        link = _rel_link(rel, node['relpath'])
        anchor = 'cls-' if node.get('kind') == 'class' else 'fn-'
        link += '#' + anchor + sanitize_id(node['name']) + '-' + str(node['line'])
        return f'- [{md_escape(ref)}]({link})'
    ns = by_ns.get(t)
    if ns and len(ns) == 1:
        return f'- [{md_escape(ref)}]({_rel_link(rel, next(iter(ns)))})'
    vs = by_var.get(t)
    if vs:
        target = rel if rel in vs else (next(iter(vs)) if len(vs) == 1 else None)
        if target is not None:
            return f'- [{md_escape(ref)}]({_rel_link(rel, target)}#variables)'
    return f'- {md_escape(ref)}'


def static_references(rel: str, fn: dict, g, call_out,
                      files, by_name, by_qname, by_ns, by_var) -> list:
    """Deterministic **References** section straight from the graph: the
    function's call targets plus the file-level variables it reads, in
    source order (deduped by name). Used when the function has no LLM
    prose (e.g. a ``--no-llm`` run). Returns [] when it references nothing.
    """
    fid = node_id_fn(rel, fn['name'], fn['line'])
    refs, seen = [], set()
    entries = sorted(call_out.get(fid, ()),
                     key=lambda t: (t[1] or 0, str(g.nodes[t[0]].get('name') or t[0])))
    for v, _line, status in entries:
        nm = g.nodes[v].get('name') or v
        # Inferred edges are kept (a unique project match) but the label
        # says so — an inference is not a verified call (P0-2).
        label = f'{nm} (inferred)' if status == 'inferred' else nm
        if label not in seen:
            seen.add(label)
            refs.append((label, status))
    if not refs:
        return []
    lines = ['**References**', '']
    has_unresolved = False
    for label, status in refs:
        if status == 'external':
            # resolution_success == false: no matching symbol in this
            # project — no link is written, highlighted orange.
            lines.append(f'- {_unresolved_span(label)}')
            has_unresolved = True
        else:
            lines.append(ref_line(rel, label, files, by_name, by_qname,
                                  by_ns, by_var))
    if has_unresolved:
        lines.append('')
        lines.append(f'> Note: {_unresolved_span("orange")} references '
                     f'could not be resolved to a symbol in this project '
                     f'(no link is written for them).')
    lines.append('')
    return lines


def _unresolved_section(rel: str, diag) -> list:
    """Per-file **Unresolved references** section (P0-2/P0-3): call sites
    the resolver could not link to a single symbol (ambiguity or no
    candidate) and imports with no matching file in the project. These are
    shown as-is — the analyzer never wrote a guessed edge for them.
    Returns [] when the file has none."""
    if not diag:
        return []
    amb = [d for d in diag.get('ambiguous_calls', []) if d.get('file') == rel]
    unc = [d for d in diag.get('unresolved_imports', [])
           if d.get('file') == rel]
    if not amb and not unc:
        return []
    lines = ['## Unresolved references', '',
             'The following references could not be resolved to a single '
             'symbol and are **not linked**; the analyzer recorded them '
             'instead of guessing:', '']
    for d in sorted(amb, key=lambda d: d.get('line') or 0):
        cands = ', '.join(f'`{c}`' for c in d.get('candidates') or []) or '—'
        lines.append(f"- line {d.get('line')}: call "
                     f"{_unresolved_span(d.get('name'))} — candidates: {cands}")
    for d in sorted(unc, key=lambda d: d.get('line') or 0):
        lines.append(f"- line {d.get('line')}: import of "
                     f"{_unresolved_span(d.get('module'))} — no matching file in the project")
    lines.append('')
    return lines


def render_file_md(finfo: dict, fn_records, var_records, summary,
                   output_root: str, graph=None, call_indexes=None,
                   sym_index=None, diag=None) -> str:
    rel = finfo['relpath']
    if sym_index is None:
        sym_index = symbol_index(graph)
    files, by_name, by_qname, by_ns, by_var = sym_index
    if call_indexes is None:
        call_out, call_in = build_call_indexes(graph)
    else:
        call_out, call_in = call_indexes
    lines = [f'# {rel}', '']
    if summary:
        lines += ['## Summary', '', summary.get('summary', ''),
                  f"**Main purpose:** {summary.get('main_purpose', '')}",
                  f"**Role in project:** {summary.get('role', '')}", '']
    else:
        lines += ['_No summary generated._', '']

    funcs = finfo.get('functions') or []
    if funcs:
        lines += ['## Functions', '']
        lines.append('| Function | Line | Parameters | Description |')
        lines.append('| --- | --- | --- | --- |')
        for fn in funcs:
            rec = fn_records.get((rel, fn['name'], fn['line']))
            desc = ''
            if rec and rec.get('prose'):
                desc = md_escape(trunc(rec['prose'].get('description', ''), 140))
            params = ', '.join(fn.get('params') or [])
            lines.append(f"| [{fn.get('qualified') or fn['name']}](#{_fn_anchor(fn)}) "
                         f"| {fn['line']} | {md_escape(params)} | {desc} |")
        lines.append('')
        for idx, fn in enumerate(funcs):
            if idx:
                lines += ['---', '']
            rec = fn_records.get((rel, fn['name'], fn['line']))
            lines.append(f"### {fn.get('qualified') or fn['name']}"
                         f" <a id=\"{_fn_anchor(fn)}\"></a>")
            lines.append('')
            lines.append(f"*{rel}:{fn['line']}"
                         + (f"-{fn['end_line']}" if fn.get('end_line', 0) > fn['line'] else '')
                         + '*')
            lines.append('')
            dev = fn.get('developer_comment')
            if dev:
                lines += ['**Developer comment**', '']
                for dl in dev.splitlines():
                    lines.append('> ' + dl if dl.strip() else '>')
                lines.append('')
            p = (rec.get('prose') if rec and isinstance(rec.get('prose'), dict)
                 else {})
            if p.get('description'):
                lines += ['**Description**', '',
                          md_escape(p['description']), '']
            else:
                lines.append('_No description generated._')
                lines.append('')
            # Parameters: names always come from the static analysis (the
            # LLM never decides which parameters exist); prose only adds
            # descriptions. Extra prose arguments are appended after the
            # static ones.
            pargs = {}
            for a in p.get('arguments') or []:
                nm = a.get('name')
                if nm:
                    pargs[str(nm)] = a
            pnames = [str(n) for n in (fn.get('params') or [])]
            for n in pargs:
                if n not in pnames:
                    pnames.append(n)
            if pnames:
                lines.append('**Parameters**')
                lines.append('')
                lines.append('| Name | Description |')
                lines.append('| --- | --- |')
                for nm in pnames:
                    d = pargs.get(nm, {}).get('description', '')
                    lines.append(f"| `{nm}` | {md_escape(d)} |")
                lines.append('')
            if p.get('outputs'):
                lines.append('**Outputs**')
                lines.append('')
                lines.append('| Name | Description |')
                lines.append('| --- | --- |')
                for o in p['outputs']:
                    nm = o.get('name') or 'return value'
                    lines.append(f"| `{md_escape(nm)}` "
                                 f"| {md_escape(o.get('description', ''))} |")
                lines.append('')
            if p.get('side_effects'):
                lines.append('**Side effects**')
                lines.append('')
                for s in p['side_effects']:
                    lines.append(f'- {md_escape(s)}')
                lines.append('')
            if p.get('references'):
                lines.append('**References**')
                lines.append('')
                for r in p['references']:
                    lines.append(ref_line(rel, r, files, by_name, by_qname,
                                          by_ns, by_var))
                lines.append('')
            elif graph is not None:
                lines += static_references(rel, fn, graph, call_out,
                                           files, by_name, by_qname,
                                           by_ns, by_var)
            if p.get('uncertainties'):
                lines.append('**Uncertainties**')
                lines.append('')
                for u in p['uncertainties']:
                    lines.append(f'- {md_escape(u)}')
                lines.append('')
            body = (fn.get('body') or '').strip()
            if body:
                lines.append('```' + fence_lang(rel))
                lines.append(body)
                lines.append('```')
                lines.append('')
            if graph is not None:
                lines += callgraph_section(rel, fn, graph, call_in)

    classes = finfo.get('classes') or []
    if classes:
        lines += ['## Classes <a id="classes"></a>', '']
        lines.append('Classes are structural symbols: constructor calls '
                     '(`Name(...)`) that resolve here are linked from the '
                     'caller\'s References section.')
        lines.append('')
        lines.append('| Class | Line |')
        lines.append('| --- | --- |')
        for c in classes:
            anchor = f"cls-{sanitize_id(c['name'])}-{c['line']}"
            lines.append(f"| <a id=\"{anchor}\">"
                         f"[{c.get('qualified') or c['name']}](#{anchor})</a> "
                         f"| {c['line']} |")
        lines.append('')

    vars_ = finfo.get('file_vars') or []
    if vars_:
        lines += ['## File-level variables <a id="variables"></a>', '']
        lines.append('| Variable | Line | Init | Description |')
        lines.append('| --- | --- | --- | --- |')
        for v in vars_:
            rec = var_records.get((rel, v['name'], v['line']))
            desc = ''
            if rec and rec.get('prose'):
                desc = md_escape(trunc(rec['prose'].get('description', ''), 140))
            lines.append(f"| `{v['name']}` | {v['line']} "
                         f"| {md_escape(v.get('init', ''))} | {desc} |")
        lines.append('')

    lines += _unresolved_section(rel, diag)
    lines.append('---')
    lines.append('_Generated by kodama-docs. Prose produced by an LLM; '
                 'structure and links generated deterministically._')
    lines.append('')
    return '\n'.join(lines)


def _analysis_summary(diag, astatus, rs=None) -> list:
    """Index footer: analysis status per file and the resolution outcome
    counts (P0-3 — failures and unresolved references stay visible in the
    docs, not just in the console). Returns [] when no data was passed."""
    if not diag and astatus is None and not rs:
        return []
    lines = ['', '## Analysis summary', '']
    if astatus is not None:
        counts = {'ok': 0, 'failed': 0, 'binary': 0}
        for st in astatus.values():
            k = st.get('status', 'ok')
            counts[k] = counts.get(k, 0) + 1
        lines.append(
            f"- Files: {len(astatus)} analyzed — {counts['ok']} ok, "
            f"{counts['failed']} failed, {counts['binary']} binary")
        for rel in sorted(k for k, v in astatus.items()
                          if v.get('status') == 'failed'):
            lines.append(f"  - `{rel}` — {astatus[rel].get('error', '')}")
    if diag:
        amb = len(diag.get('ambiguous_calls', []))
        extc = len(diag.get('external_calls', []))
        unc = len(diag.get('unresolved_imports', []))
        inf = len(diag.get('inferred_calls', []))
        lines.append(
            f"- Call references: {extc} external, {inf} inferred, "
            f"**{amb} ambiguous** (recorded, not linked), "
            f"{unc} unresolved import(s)")
    if rs:
        cs, im = rs.get('calls', {}), rs.get('imports', {})
        cok = cs.get('success', 0)
        cfail = cs.get('failed', 0)
        iok = im.get('success', 0)
        ifail = im.get('failed', 0)
        lines.append(
            f"- Resolution: **{cok}/{cok + cfail}** call references and "
            f"**{iok}/{iok + ifail}** imports resolved successfully. "
            f"References that did not resolve are highlighted "
            f"{_unresolved_span('orange')} on each page.")
    lines.append('')
    return lines


def _manual_section(pages):
    """The section-0 **Manual documentation** block (a link table), placed
    above the generated-files table. Links are relative to index.md, so the
    pages (copied to <output_dir>/manual/) are ``manual/<rel>``. Returns []
    when there are no pages."""
    if not pages:
        return []
    lines = ['## Manual documentation', '',
             '| Page |',
             '| --- |']
    for p in pages:
        label = p.get('title') or p['rel']
        lines.append(f"| [{label}]({enc_path('manual/' + p['rel'])}) |")
    lines.append('')
    return lines


def render_index(finfos, output_root: str, diag=None, astatus=None,
                 rs=None, manual_pages=None) -> str:
    lines = ['# Documentation index', '']
    lines += _manual_section(manual_pages)
    lines += [f'{len(finfos)} files documented.', '',
              '| File | Lines | Functions | Variables |',
              '| --- | --- | --- | --- |']
    for finfo in finfos:
        rel = finfo['relpath']
        mdname = rel.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        lines.append(
            f"| [{rel}]({enc_path('files/' + rel + '.md')}) "
            f"| {finfo.get('lines', '?')} "
            f"| {len(finfo.get('functions') or [])} "
            f"| {len(finfo.get('file_vars') or [])} |")
    lines.append('')
    lines += _analysis_summary(diag, astatus, rs)
    lines.append('---')
    lines.append('_Generated by kodama-docs._')
    lines.append('')
    return '\n'.join(lines)


def write_md(text: str, output_root: str, rel: str):
    path = os.path.join(output_root, 'files', rel + '.md')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return path
