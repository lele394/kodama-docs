"""Walk a tree-sitter-lua tree into the neutral backend records."""
from backends._shared import _all_comments, _dev_comment, parse_llm_directive

from .nodes import (
    callee,
    classify_value,
    comment_text,
    dotted,
    function_params,
    ident,
    node_row,
    node_text,
    require_module,
    string_value,
    var_names,
)
from .parser import parser


def extract(source: str, relpath: str) -> dict:
    source = source.removeprefix('\ufeff')
    root = parser.parse(source.encode('utf-8')).root_node
    comments = _all_comments(root)
    lines = source.splitlines()
    fns, file_vars, calls, imports = [], [], [], []
    seen_fn, seen_call = set(), set()
    import_mods = []

    def add_fn(name, qual, line, end_line, params, vararg, dev=None):
        fname = name or 'anon'
        fid = f'fn:{relpath}::{fname}@{line}'
        if fid in seen_fn:
            return
        seen_fn.add(fid)
        a, b = line - 1, min(end_line, len(lines))
        body = '\n'.join(lines[a:b])
        dev, skip = parse_llm_directive(dev)
        rec = {'id': fid, 'name': fname, 'qualified': qual or fname,
               'line': line, 'end_line': end_line,
               'params': list(params), 'vararg': bool(vararg),
               'body': body, 'developer_comment': dev}
        if skip:
            rec['skip_llm'] = True
        fns.append(rec)

    def note_call(node):
        name, method = callee(node)
        if not name:
            return
        line = node_row(node)
        if (name, line) in seen_call:
            return
        seen_call.add((name, line))
        calls.append({'callee': name, 'line': line, 'method': method})

    def maybe_import(node, depth):
        if depth > 1:
            return
        name, _method = callee(node)
        if not name or name.rsplit('.', 1)[-1] not in ('require', 'dofile'):
            return
        args = node.child_by_field_name('arguments')
        if args is None or args.type != 'arguments':
            return
        for c in args.children:
            if c.type == 'string':
                val = string_value(c)
                if val and val not in import_mods:
                    import_mods.append(val)
                    imports.append({'module': val, 'line': node_row(c)})
                break

    def walk_assign(asm, depth, is_local):
        names, first_val = [], None
        for c in asm.children:
            if c.type == 'variable_list':
                names = var_names(c)
            elif c.type == 'expression_list' and first_val is None:
                for v in c.children:
                    if v.type not in ('(', ')'):
                        first_val = v
                        break
        if is_local and depth == 0:
            # `local A = require('mod')`: record the loaded module so
            # `A:method()` can be resolved to mod's method (one alias per
            # module — only attach it for a single declared name)
            mod = require_module(first_val) if len(names) == 1 else None
            dev, skip = parse_llm_directive(
                _dev_comment(comments, node_row(asm), comment_text))
            for nm in names:
                rec = {'name': nm, 'line': node_row(asm),
                       'init': classify_value(first_val),
                       'developer_comment': dev}
                if first_val is not None:
                    val = node_text(first_val).strip()
                    if val:
                        rec['value'] = val[:400]
                if mod:
                    rec['module'] = mod
                if skip:
                    rec['skip_llm'] = True
                file_vars.append(rec)
        # walk every value (closures get the first declared name, like the
        # previous hand-rolled extractor)
        exprs = None
        for c in asm.children:
            if c.type == 'expression_list':
                exprs = c
                break
        if exprs is not None:
            for v in exprs.children:
                if v.type == 'function_definition':
                    walk(v, depth + 1, names[0] if names else None)
                else:
                    walk(v, depth, None)

    def walk(node, depth, closure_name):
        t = node.type
        if t == 'function_declaration':
            nm = node.child_by_field_name('name')
            fname = qual = None
            is_method = nm is not None and \
                nm.type == 'method_index_expression'
            identifier = ident(nm)
            if identifier:
                fname = qual = identifier
            else:
                parts = dotted(nm, allow_method=is_method) \
                    if nm is not None else None
                if parts:
                    fname, qual = parts[-1], '.'.join(parts)
            if fname:
                params, vararg = function_params(node)
                if is_method and (not params or params[0] != 'self'):
                    # colon methods receive an implicit `self` first argument
                    params = ['self'] + list(params)
                add_fn(fname, qual, node_row(node),
                       node.end_point[0] + 1, params, vararg,
                       _dev_comment(comments, node_row(node), comment_text))
            body = node.child_by_field_name('body')
            if body is not None:
                walk(body, depth + 1, None)
            return

        if t == 'function_definition':
            params, vararg = function_params(node)
            add_fn(closure_name, closure_name, node_row(node),
                   node.end_point[0] + 1, params, vararg,
                   _dev_comment(comments, node_row(node), comment_text))
            body = node.child_by_field_name('body')
            if body is not None:
                walk(body, depth + 1, None)
            return

        if t == 'variable_declaration':
            for c in node.children:
                if c.type == 'assignment_statement':
                    walk_assign(c, depth, True)
            return

        if t == 'assignment_statement':
            walk_assign(node, depth, False)
            return

        if t == 'function_call':
            note_call(node)
            maybe_import(node, depth)
            base = None
            name, _method = callee(node)
            if name:
                base = name.rsplit('.', 1)[-1]
            args = node.child_by_field_name('arguments')
            if args is not None:
                for c in args.children:
                    if c.type == 'function_definition':
                        walk(c, depth + 1, base)
                    else:
                        walk(c, depth, None)
            return

        if t == 'table_constructor':
            for c in node.children:
                if c.type == 'field':
                    key_node = c.child_by_field_name('name')
                    key = ident(key_node)
                    if key is None and key_node is not None \
                            and key_node.type == 'string':
                        key = node_text(key_node).strip('"').strip("'")
                    val = c.child_by_field_name('value')
                    if val is not None:
                        walk(val, depth, key)
                    continue
                walk(c, depth, None)
            return

        for c in node.children:
            walk(c, depth, None)

    walk(root, 0, None)
    return {'functions': fns, 'file_vars': file_vars,
            'calls': calls, 'imports': imports}
