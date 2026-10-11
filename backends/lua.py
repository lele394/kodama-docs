"""Lua extraction backend (tree-sitter based).

Parsing is delegated to the official tree-sitter-lua grammar; this module
only walks the concrete syntax tree and projects it into the common shape
documented in backends/__init__.py. No hand-rolled tokenizer/parser.

Record shapes (1-based lines, stable across backends):
    functions: [{id, name, qualified, line, end_line, params, vararg, body,
                 developer_comment: str|None}]
    file_vars: [{name, line, init: empty|table|string|number|function|call|expr}]
    calls:     [{callee, line, method: str|None}]   (method call: callee is
                                                    the object part, method
                                                    the method name)
    imports:   [{module, line}]
"""
import tree_sitter_lua as tslua
from tree_sitter import Language, Parser

from backends import _all_comments, _dev_comment

BUILTIN_NAMES = {
    'print', 'pairs', 'ipairs', 'next', 'type', 'tonumber', 'tostring',
    'pcall', 'xpcall', 'error', 'assert', 'select', 'unpack', 'rawget',
    'rawset', 'rawequal', 'setmetatable', 'getmetatable', 'require',
    'dofile', 'collectgarbage', 'self', '_G', '_VERSION', 'math', 'string',
    'table', 'os', 'io', 'coroutine', 'bit32', 'utf8', 'module',
}

_parser = Parser(Language(tslua.language()))


def _row(node):
    return node.start_point[0] + 1


def _text(node):
    return node.text.decode('utf-8')


def _comment_text(node):
    """Cleaned comment text: the grammar's comment_content child, stripped
    (line `--` prefixes and `--[[ ... ]]` markers are not part of it)."""
    for c in node.children:
        if c.type == 'comment_content':
            return _text(c).strip()
    return _text(node).strip()


def _ident(node):
    return _text(node) if node is not None and node.type == 'identifier' else None


def _dotted(node):
    """dot_index_expression -> ['a', 'b', 'c']; None if not a plain chain."""
    parts = []
    while node is not None:
        if node.type == 'identifier':
            parts.insert(0, _text(node))
            return parts
        if node.type == 'dot_index_expression':
            name = node.children[-1]
            if name.type != 'identifier':
                return None
            parts.insert(0, _text(name))
            node = node.children[0]
            continue
        return None
    return None


def _callee(node):
    """function_call -> (callee_name_or_None, method_name_or_None).

    A plain call `print(1)` -> ('print', None); a dotted call
    `A.b(1)` -> ('A.b', None); a method call `x:m(1)` -> ('x', 'm').
    """
    fn = node.child_by_field_name('name')
    if fn is None:
        return None, None
    if fn.type == 'identifier':
        return _text(fn), None
    if fn.type == 'dot_index_expression':
        parts = _dotted(fn)
        return ('.'.join(parts), None) if parts else (None, None)
    if fn.type == 'method_index_expression':
        method = _ident(fn.child_by_field_name('method'))
        if not method:
            return None, None
        table = fn.child_by_field_name('table')
        if table is not None and table.type == 'identifier':
            return _text(table), method
        parts = _dotted(table) if table is not None else None
        if parts:
            return '.'.join(parts), method
        return None, method
    return None, None


def _params(fn_node):
    """function_declaration/function_definition -> (params, vararg)."""
    params = fn_node.child_by_field_name('parameters')
    if params is None:
        return [], False
    names, vararg = [], False
    for c in params.children:
        if c.type == 'identifier':
            names.append(_text(c))
        elif c.type == 'vararg_expression':
            vararg = True
    return names, vararg


def _classify(node):
    if node is None:
        return 'empty'
    ty = node.type
    if ty == 'table_constructor':
        return 'table'
    if ty == 'string':
        return 'string'
    if ty == 'number':
        return 'number'
    if ty == 'function_definition':
        return 'function'
    if ty == 'function_call':
        return 'call'
    return 'expr'


def _var_names(var_list):
    """variable_list -> first declared name per target (identifier or the
    last part of a dotted target), in order."""
    names = []
    for c in var_list.children:
        if c.type == 'identifier':
            names.append(_text(c))
        elif c.type == 'dot_index_expression':
            parts = _dotted(c)
            names.append(parts[-1] if parts else None)
        else:
            names.append(None)
    return [n for n in names if n]


def _string_value(node):
    for c in node.children:
        if c.type == 'string_content':
            return _text(c).strip()
    return None


def extract(source: str, relpath: str) -> dict:
    if source.startswith('\ufeff'):
        source = source[1:]
    root = _parser.parse(source.encode('utf-8')).root_node
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
        fns.append({'id': fid, 'name': fname, 'qualified': qual or fname,
                    'line': line, 'end_line': end_line,
                    'params': list(params), 'vararg': bool(vararg),
                    'body': body, 'developer_comment': dev})

    def note_call(node):
        name, method = _callee(node)
        if not name:
            return
        line = _row(node)
        if (name, line) in seen_call:
            return
        seen_call.add((name, line))
        calls.append({'callee': name, 'line': line, 'method': method})

    def maybe_import(node, depth):
        if depth > 1:
            return
        name, _m = _callee(node)
        if not name or name.rsplit('.', 1)[-1] not in ('require', 'dofile'):
            return
        args = node.child_by_field_name('arguments')
        if args is None or args.type != 'arguments':
            return
        for c in args.children:
            if c.type == 'string':
                val = _string_value(c)
                if val and val not in import_mods:
                    import_mods.append(val)
                    imports.append({'module': val, 'line': _row(c)})
                break

    def walk_assign(asm, depth, is_local):
        names, first_val = [], None
        for c in asm.children:
            if c.type == 'variable_list':
                names = _var_names(c)
            elif c.type == 'expression_list' and first_val is None:
                for v in c.children:
                    if v.type not in ('(', ')'):
                        first_val = v
                        break
        if is_local and depth == 0:
            for nm in names:
                file_vars.append({'name': nm, 'line': _row(asm),
                                  'init': _classify(first_val)})
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
            ident = _ident(nm)
            if ident:
                fname = qual = ident
            else:
                parts = _dotted(nm) if nm is not None else None
                if parts:
                    fname, qual = parts[-1], '.'.join(parts)
            if fname:
                params, vararg = _params(node)
                add_fn(fname, qual, _row(node), node.end_point[0] + 1,
                       params, vararg,
                       _dev_comment(comments, _row(node), _comment_text))
            body = node.child_by_field_name('body')
            if body is not None:
                walk(body, depth + 1, None)
            return

        if t == 'function_definition':
            params, vararg = _params(node)
            add_fn(closure_name, closure_name, _row(node),
                   node.end_point[0] + 1, params, vararg,
                   _dev_comment(comments, _row(node), _comment_text))
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
            name, _m = _callee(node)
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
                    key = _ident(key_node)
                    if key is None and key_node is not None \
                            and key_node.type == 'string':
                        key = _text(key_node).strip('"').strip("'")
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
