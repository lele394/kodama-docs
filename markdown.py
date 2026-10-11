"""Deterministic markdown output: anchors, links, call graphs, per-file
pages and the index. No LLM prose except the record strings passed in.
"""
import os

from graph import node_id_fn
from util import fence_lang, sanitize_id, trunc


def md_escape(s: str) -> str:
    return str(s).replace('|', '\\|')


def _fn_anchor(fn: dict) -> str:
    return f"fn-{sanitize_id(fn['name'])}-{fn['line']}"


def _rel_link(from_rel: str, to_rel: str) -> str:
    """Relative markdown link from files/<from_rel>.md to files/<to_rel>.md."""
    p = os.path.relpath(to_rel + '.md', os.path.dirname(from_rel) or '.')
    return p.replace(os.sep, '/')


def callers_of(g, fn_id: str):
    """Deterministic list of call sites targeting a function node.

    Each item is a dict: file (caller relpath), name/qualified/line (the
    calling function; all None when the call happens at file level) and
    call (the call-site line). Sorted by (file, call, name).
    """
    out = []
    for u, v, d in g.edges(data=True):
        if d.get('type') != 'CALLS' or v != fn_id:
            continue
        s = g.nodes[u]
        if s.get('kind') == 'function':
            out.append({'file': s.get('relpath') or '',
                        'name': s.get('name') or '',
                        'qualified': s.get('qualified') or s.get('name') or '',
                        'line': s.get('line'),
                        'call': d.get('line')})
        else:
            out.append({'file': s.get('relpath') or '',
                        'name': None, 'qualified': None, 'line': None,
                        'call': d.get('line')})
    out.sort(key=lambda c: (c['file'], c['call'] or 0, c['name'] or ''))
    return out


def callgraph_section(rel: str, fn: dict, g) -> list:
    """Markdown lines for the deterministic Call graph section (or [])."""
    sites = callers_of(g, node_id_fn(rel, fn['name'], fn['line']))
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


def _symbol_index(g):
    """Deterministic link targets for References bullets: file relpaths,
    function nodes by name / qualified name, and module namespaces
    (qualified-name prefixes) -> the file(s) they live in (from the graph)."""
    files, by_name, by_qname, by_ns, by_var = set(), {}, {}, {}, {}
    if g is None:
        return files, by_name, by_qname, by_ns, by_var
    for nid, nd in g.nodes(data=True):
        kind = nd.get('kind')
        if kind not in ('function', 'variable'):
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
        link += '#fn-' + sanitize_id(node['name']) + '-' + str(node['line'])
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


def render_file_md(finfo: dict, fn_records, var_records, summary,
                   output_root: str, graph=None) -> str:
    rel = finfo['relpath']
    files, by_name, by_qname, by_ns, by_var = _symbol_index(graph)
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
            if rec and rec.get('prose'):
                p = rec['prose']
                if p.get('description'):
                    lines += ['**Description**', '',
                              md_escape(p['description']), '']
                if p.get('arguments'):
                    lines.append('**Parameters**')
                    lines.append('')
                    lines.append('| Name | Description |')
                    lines.append('| --- | --- |')
                    for a in p['arguments']:
                        lines.append(f"| `{a.get('name', '')}` "
                                     f"| {md_escape(a.get('description', ''))} |")
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
                if p.get('uncertainties'):
                    lines.append('**Uncertainties**')
                    lines.append('')
                    for u in p['uncertainties']:
                        lines.append(f'- {md_escape(u)}')
                    lines.append('')
            else:
                lines.append('_No description generated._')
                lines.append('')
            body = (fn.get('body') or '').strip()
            if body:
                lines.append('```' + fence_lang(rel))
                lines.append(body)
                lines.append('```')
                lines.append('')
            if graph is not None:
                lines += callgraph_section(rel, fn, graph)

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

    lines.append('---')
    lines.append('_Generated by doc_maker. Prose produced by an LLM; '
                 'structure and links generated deterministically._')
    lines.append('')
    return '\n'.join(lines)


def render_index(finfos, output_root: str) -> str:
    lines = ['# Documentation index', '',
             f'{len(finfos)} files documented.', '',
             '| File | Lines | Functions | Variables |',
             '| --- | --- | --- | --- |']
    for finfo in finfos:
        rel = finfo['relpath']
        mdname = rel.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        lines.append(
            f"| [{rel}](files/{rel}.md) | {finfo.get('lines', '?')} "
            f"| {len(finfo.get('functions') or [])} "
            f"| {len(finfo.get('file_vars') or [])} |")
    lines.append('')
    lines.append('---')
    lines.append('_Generated by doc_maker._')
    lines.append('')
    return '\n'.join(lines)


def write_md(text: str, output_root: str, rel: str):
    path = os.path.join(output_root, 'files', rel + '.md')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return path
