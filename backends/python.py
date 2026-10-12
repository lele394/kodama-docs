"""Python extraction backend (tree-sitter based).

Parsing is delegated to the official tree-sitter-python grammar; this module
only walks the concrete syntax tree and projects it into the common shape
documented in backends/__init__.py. No hand-rolled tokenizer/parser.

Record shapes (1-based lines, identical to the Lua backend):
    functions: [{id, name, qualified, line, end_line, params, vararg, body,
                 developer_comment: str|None}]
    file_vars: [{name, line, init: empty|table|string|number|function|call|expr}]
    calls:     [{callee, line, method: str|None}]
    imports:   [{module, line}]
"""
import re

import tree_sitter_python as tspy
from tree_sitter import Language, Parser

from backends import _all_comments, _dev_comment

BUILTIN_NAMES = {
    # python builtins
    'print', 'len', 'range', 'open', 'super', 'isinstance', 'issubclass',
    'hasattr', 'getattr', 'setattr', 'delattr', 'callable', 'getattr',
    'abs', 'all', 'any', 'bool', 'dict', 'dir', 'divmod', 'enumerate',
    'filter', 'float', 'format', 'frozenset', 'int', 'isinstance', 'iter',
    'list', 'map', 'max', 'min', 'next', 'object', 'ord', 'pow', 'repr',
    'reversed', 'round', 'set', 'slice', 'sorted', 'str', 'sum', 'tuple',
    'type', 'zip', 'property', 'staticmethod', 'classmethod', 'Exception',
    'ValueError', 'TypeError', 'RuntimeError', 'AttributeError', 'KeyError',
    'IndexError', 'LookupError', 'OSError', 'IOError', 'SystemExit',
    'StopIteration', 'NotImplementedError', 'self', 'cls',
    # common stdlib modules (treated as external, not cross-file links)
    'os', 'sys', 're', 'json', 'hashlib', 'urllib', 'threading', 'atexit',
    'argparse', 'time', 'io', 'math', 'enum', 'itertools', 'functools',
    'collections', 'contextlib', 'abc', 'typing', 'warnings', 'shutil',
    'tempfile', 'subprocess', 'glob', 'copy', 'types', 'importlib',
    'logging', 'pathlib', 'uuid', 'base64', 'platform', 'getpass',
    'secrets', 'string', 'textwrap', 'unicodedata', 'weakref', 'heapq',
    'bisect', 'array', 'queue', 'multiprocessing', 'signal', 'socket',
    'struct', 'pickle', 'csv', 'xml', 'html', 'email', 'http', 'asyncio',
    'concurrent', 'dataclasses', 'unittest', 'random', 'statistics',
    'decimal', 'fractions', 'calendar', 'datetime', 'zoneinfo', 'graphlib',
}

_parser = Parser(Language(tspy.language()))

# parameter node types that may hide the name one level down
_PARAM_TYPES = ('identifier', 'typed_parameter', 'default_parameter',
                'typed_default_parameter', 'multiple_parameter',
                'keyword_parameter', 'list_splat_parameter')


def _row(node):
    return node.start_point[0] + 1


def _text(node):
    return node.text.decode('utf-8')


def _comment_text(node):
    """Cleaned comment text: leading '#' marker(s) and one space removed."""
    return re.sub(r'^\s*#+\s?', '', _text(node)).strip()


def _dotted(node):
    """dotted_name / identifier -> ['a', 'b', 'c']; None if not a plain chain."""
    parts = []
    while node is not None and node.type in ('dotted_name', 'identifier'):
        if node.type == 'identifier':
            parts.insert(0, _text(node))
            return parts
        ident = node.child_by_field_name('attribute')
        if ident is None:  # single-identifier dotted_name
            for c in node.children:
                if c.type == 'identifier':
                    parts.insert(0, _text(c))
                    return parts
            return None
        parts.insert(0, _text(ident))
        node = node.child_by_field_name('object')
        if node is None:
            return parts
    return parts or None


def _params(node):
    """function_definition -> (params, vararg)."""
    params = node.child_by_field_name('parameters')
    if params is None:
        return [], False
    names, vararg = [], False
    for c in params.children:
        if c.type in _PARAM_TYPES:
            ident = c if c.type == 'identifier' else None
            if ident is None:
                for cc in c.children:
                    if cc.type == 'identifier':
                        ident = cc
                        break
            if ident is not None:
                names.append(_text(ident))
            if '*' in _text(c):
                vararg = True
    return names, vararg


def _classify(node):
    if node is None:
        return 'empty'
    t = node.type
    if t in ('dictionary', 'list', 'set', 'list_display', 'set_display', 'tuple'):
        return 'table'
    if t == 'string':
        return 'string'
    if t in ('integer', 'float'):
        return 'number'
    if t in ('lambda', 'function_definition'):
        return 'function'
    if t == 'call':
        return 'call'
    return 'expr'


def extract(source: str, relpath: str) -> dict:
    if source.startswith('\ufeff'):
        source = source[1:]
    root = _parser.parse(source.encode('utf-8')).root_node
    comments = _all_comments(root)
    lines = source.splitlines()
    fns, file_vars, calls, imports = [], [], [], []
    seen_fn, seen_call, seen_var = set(), set(), set()
    import_mods = []

    def add_fn(name, line, end_line, params, vararg, dev=None):
        fid = f'fn:{relpath}::{name}@{line}'
        if fid in seen_fn:
            return
        seen_fn.add(fid)
        a, b = line - 1, min(end_line, len(lines))
        body = '\n'.join(lines[a:b])
        fns.append({'id': fid, 'name': name, 'qualified': name,
                    'line': line, 'end_line': end_line,
                    'params': list(params), 'vararg': bool(vararg),
                    'body': body, 'developer_comment': dev})

    def note_call(node):
        fn = node.child_by_field_name('function')
        if fn is None:
            return
        name, method = None, None
        if fn.type == 'identifier':
            name = _text(fn)
        elif fn.type == 'attribute':
            method = fn.child_by_field_name('attribute')
            if method is not None:
                method = _text(method)
                parts = _dotted(fn.child_by_field_name('value'))
                if parts:
                    name = '.'.join(parts)
                else:
                    name = 'expr'
        if not name or name == 'expr':
            return
        line = _row(node)
        if (name, line) in seen_call:
            return
        seen_call.add((name, line))
        calls.append({'callee': name, 'line': line, 'method': method})

    def note_import(module, line):
        if module and module not in import_mods:
            import_mods.append(module)
            imports.append({'module': module, 'line': line})

    def note_var(name, line, value):
        if not name or name in seen_var:
            return
        seen_var.add(name)
        file_vars.append({'name': name, 'line': line,
                          'init': _classify(value)})

    def walk(node, depth):
        t = node.type
        if t == 'function_definition':
            nm = node.child_by_field_name('name')
            if nm is not None:
                name = _text(nm)
                params, vararg = _params(node)
                add_fn(name, _row(node), node.end_point[0] + 1,
                       params, vararg,
                       _dev_comment(comments, _row(node), _comment_text))
            body = node.child_by_field_name('body')
            if body is not None:
                walk(body, depth + 1)
            return

        if t == 'assignment' and depth == 0:
            left = node.child_by_field_name('left')
            value = node.child_by_field_name('right')
            if left is not None and left.type == 'identifier':
                note_var(_text(left), _row(node), value)
            for c in node.children:
                walk(c, depth)
            return

        if t == 'annotated_assignment' and depth == 0:
            left = node.child_by_field_name('left')
            value = node.child_by_field_name('value')
            if left is not None and left.type == 'identifier':
                note_var(_text(left), _row(node), value)
            for c in node.children:
                walk(c, depth)
            return

        if t == 'call':
            note_call(node)

        if t == 'import_statement':
            for c in node.children:
                if c.type == 'dotted_name':
                    parts = _dotted(c)
                    if parts:
                        note_import('.'.join(parts), _row(c))
            for c in node.children:
                walk(c, depth)
            return

        if t == 'import_from_statement':
            mod = node.child_by_field_name('module_name')
            if mod is not None:
                parts = _dotted(mod)
                if parts:
                    note_import('.'.join(parts), _row(node))
            for c in node.children:
                walk(c, depth)
            return

        for c in node.children:
            walk(c, depth)

    walk(root, 0)
    return {'functions': fns, 'file_vars': file_vars,
            'calls': calls, 'imports': imports}
