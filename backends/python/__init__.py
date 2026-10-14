"""Python extraction backend (tree-sitter based).

Parsing is delegated to the official tree-sitter-python grammar; this module
only walks the concrete syntax tree and projects it into the common shape
documented in backends/backend_design.md. No hand-rolled tokenizer/parser.

Record shapes (1-based lines, identical to the Lua backend):
    functions: [{id, name, qualified, line, end_line, params, vararg, body,
                 developer_comment: str|None}]
    file_vars: [{name, line, init: empty|table|string|number|function|call|expr}]
    calls:     [{callee, line, method: str|None}]
    imports:   [{module, line, bind?: str, name?: str}]
        -- `bind` is the local name this import binds in the importing file
        -- (`import x as a` -> 'a'; `from m import n` -> 'n'; absent for a
        -- plain `import x`, where the default is the module's last
        -- segment). `name` is the target symbol inside the module for a
        -- from-import (`from m import n` -> 'n'; `from m import n as a`
        -- -> 'n'). Together they let the graph phase resolve `a.method()`
        -- and bare `n()` to that module's definitions.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import tree_sitter_python as tspy
from tree_sitter import Language, Parser

from backends._shared import _all_comments, _dev_comment

BUILTIN_NAMES = {
    # python builtins
    'print', 'len', 'range', 'open', 'super', 'isinstance', 'issubclass',
    'hasattr', 'getattr', 'setattr', 'delattr', 'callable',
    'abs', 'all', 'any', 'bool', 'dict', 'dir', 'divmod', 'enumerate',
    'filter', 'float', 'format', 'frozenset', 'int', 'iter',
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

# parameter node types that may hide the name one level down.
# Older tree-sitter-python (<=0.20) used multiple_parameter /
# keyword_parameter / list_splat_parameter; the 0.25 grammar renamed them to
# list_splat_pattern / dictionary_splat_pattern. We accept both so the backend
# is stable across grammar builds.
_PARAM_TYPES = ('identifier', 'typed_parameter', 'default_parameter',
                'typed_default_parameter', 'multiple_parameter',
                'keyword_parameter', 'list_splat_parameter',
                'list_splat_pattern', 'dictionary_splat_pattern')


def _row(node):
    return node.start_point[0] + 1


def _text(node):
    return node.text.decode('utf-8')


def _comment_text(node):
    """Cleaned comment text: leading '#' marker(s) and one space removed."""
    return re.sub(r'^\s*#+\s?', '', _text(node)).strip()


def _dotted(node):
    """dotted_name / identifier / name -> ['a', 'b', 'c']; None otherwise.

    `name` is the tree-sitter-python 0.25 node for a plain identifier
    (e.g. the receiver of `obj.method()` or `math.sqrt()`). A
    `dotted_name` is split on its dots: this is robust across grammar
    builds where the `object`/`attribute` fields are absent, and yields the
    full path (`a.b.c` -> ['a', 'b', 'c']) so nested-package imports like
    `from physics.body import Body` resolve to the real module."""
    if node is None:
        return None
    if node.type in ('identifier', 'name'):
        t = _text(node).strip()
        return [t] if t else None
    if node.type == 'dotted_name':
        parts = [p for p in _text(node).split('.') if p]
        return parts or None
    return None


def _dotted_path(node):
    """Full dotted path of a STATIC receiver, or None when it is computed
    at runtime.

    Handles the three shapes tree-sitter-python produces:
      * ``identifier`` / ``name``  -> ``['a']``
      * ``dotted_name``            -> ``['a', 'b', 'c']``
      * nested ``attribute`` chains -> ``['a', 'b', 'c']``

    A receiver that is a call, a subscript, a lambda, ... is dynamic: there
    is no static target, so this returns ``None`` (the call is still recorded
    and surfaced as an external ``?.method`` reference)."""
    if node is None:
        return None
    t = node.type
    if t in ('identifier', 'name'):
        s = _text(node).strip()
        return [s] if s else None
    if t == 'dotted_name':
        return [p for p in _text(node).split('.') if p] or None
    if t == 'attribute':
        obj = node.child_by_field_name('object')
        if obj is None:
            for c in node.children:
                if c.type in ('attribute', 'identifier', 'name'):
                    obj = c
                    break
        base = _dotted_path(obj)
        attr = node.child_by_field_name('attribute')
        if attr is None:
            # The attribute is the *last* identifier child (the receiver is
            # the first); a naive first-match would grab the receiver.
            attr = next((c for c in reversed(node.children)
                         if c.type in ('identifier', 'name')), None)
        if base is None or attr is None:
            return None
        a = _text(attr).strip()
        return base + ([a] if a else [])
    return None


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
            # A variadic parameter is one whose text *starts* with '*'
            # (`*args` / `**kwargs`); a mere '*' appearing anywhere in a
            # default value (`size=1024*1024`, `sep='*'`) must NOT trigger it.
            if _text(c).lstrip().startswith('*'):
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
    fns, file_vars, calls, imports, classes = [], [], [], [], []
    seen_fn, seen_call, seen_var, seen_cls = set(), set(), set(), set()
    import_mods = []

    def add_fn(name, line, end_line, params, vararg, dev=None,
               qualified=None):
        fid = f'fn:{relpath}::{name}@{line}'
        if fid in seen_fn:
            return
        seen_fn.add(fid)
        a, b = line - 1, min(end_line, len(lines))
        body = '\n'.join(lines[a:b])
        fns.append({'id': fid, 'name': name, 'qualified': qualified or name,
                    'line': line, 'end_line': end_line,
                    'params': list(params), 'vararg': bool(vararg),
                    'body': body, 'developer_comment': dev})

    def note_call(node):
        fn = node.child_by_field_name('function')
        if fn is None:
            return
        name, method = None, None
        if fn.type == 'identifier':
            name = _text(fn).strip() or None
        elif fn.type == 'attribute':
            method_node = fn.child_by_field_name('attribute')
            if method_node is None:  # older grammar field name
                method_node = fn.child_by_field_name('value')
            if method_node is not None:
                method = _text(method_node)
                receiver = fn.child_by_field_name('object')
                if receiver is None:
                    receiver = fn.child_by_field_name('value')
                # A static dotted receiver is a resolvable target (e.g.
                # `deep.pack.mod` in `deep.pack.mod.launch(...)`); a dynamic
                # one (call / subscript / lambda) is not — keep the call
                # VISIBLE as external `?.method` rather than dropping it.
                parts = _dotted_path(receiver)
                name = '.'.join(parts) if parts else None
            else:
                parts = _dotted_path(fn)
                name = '.'.join(parts) if parts else None
        else:
            # `getattr(obj, 'x')()` and the like: the callee is itself a
            # computed expression — no static target, surface as external `?`.
            name, method = None, None
        line = _row(node)
        key = (name, method, line)
        if key in seen_call:
            return
        seen_call.add(key)
        calls.append({'callee': name, 'line': line, 'method': method})

    def note_import(module, line, bind=None, name=None, level=0):
        key = (module, bind, name, level)
        if key not in import_mods:
            import_mods.append(key)
            rec = {'module': module, 'line': line, 'level': level}
            if bind:
                rec['bind'] = bind
            if name:
                rec['name'] = name
            imports.append(rec)

    def note_var(name, line, value):
        if not name or name in seen_var:
            return
        seen_var.add(name)
        file_vars.append({'name': name, 'line': line,
                          'init': _classify(value)})

    def record_function(fn_node, anchor_line, depth, qual):
        """Record a function/method (name, params, vararg, developer comment,
        qualified name) and walk its parameters, return annotation and body so
        calls inside default arguments / annotations are not dropped.

        ``anchor_line`` is the line the developer comment is glued against:
        the ``def`` line for a plain function, the first decorator line for a
        decorated one (so a comment above ``@decorator`` is still captured).
        ``qual`` is the tuple of enclosing class names (innermost last); it
        yields a qualified name like ``Vec3.normalize`` or ``A.B.m``."""
        nm = fn_node.child_by_field_name('name')
        if nm is not None:
            name = _text(nm)
            params, vararg = _params(fn_node)
            qualified = '.'.join(qual + (name,)) if qual else name
            add_fn(name, _row(fn_node), fn_node.end_point[0] + 1,
                   params, vararg,
                   _dev_comment(comments, anchor_line, _comment_text),
                   qualified)
        for field in ('parameters', 'return_type'):
            part = fn_node.child_by_field_name(field)
            if part is not None:
                walk(part, depth + 1, qual)
        body = fn_node.child_by_field_name('body')
        if body is not None:
            walk(body, depth + 1, qual)

    def walk(node, depth, qual=()):
        t = node.type
        if t == 'function_definition':
            record_function(node, _row(node), depth, qual)
            return

        if t == 'decorated_definition':
            fn_node = next((c for c in node.children
                            if c.type == 'function_definition'), None)
            if fn_node is not None:
                # Glue the developer comment against the FIRST decorator line
                # (the top of this block), not the def line.
                record_function(fn_node, _row(node), depth, qual)
                return
            # A decorated non-function (rare) falls through to the generic walk.

        if t == 'assignment' and depth == 0:
            left = node.child_by_field_name('left')
            value = node.child_by_field_name('right')
            if left is not None and left.type == 'identifier':
                note_var(_text(left), _row(node), value)
            for c in node.children:
                walk(c, depth, qual)
            return

        if t == 'annotated_assignment' and depth == 0:
            left = node.child_by_field_name('left')
            value = node.child_by_field_name('value')
            if left is not None and left.type == 'identifier':
                note_var(_text(left), _row(node), value)
            for c in node.children:
                walk(c, depth, qual)
            return

        if t == 'call':
            note_call(node)

        if t == 'import_statement':
            # `import a.b` -> dotted_name; `import a.b as x` -> aliased_import
            # (fields: name = module dotted_name, alias = local name).
            for c in node.children:
                if c.type == 'dotted_name':
                    parts = _dotted(c)
                    if parts:
                        note_import('.'.join(parts), _row(node))
                elif c.type == 'aliased_import':
                    tgt = c.child_by_field_name('name')
                    al = c.child_by_field_name('alias')
                    parts = _dotted(tgt) if tgt is not None else None
                    if parts:
                        note_import('.'.join(parts), _row(node),
                                    bind=_text(al) if al is not None else None)
            return

        if t == 'import_from_statement':
            mod_node = node.child_by_field_name('module_name')
            level = 0
            module = None
            if mod_node is not None:
                if mod_node.type == 'relative_import':
                    prefix = mod_node.child_by_field_name('import_prefix')
                    if prefix is None:
                        for cc in mod_node.children:
                            if cc.type == 'import_prefix':
                                prefix = cc
                                break
                    level = len(_text(prefix).strip()) if prefix else 1
                    modpart = mod_node.child_by_field_name('module')
                    if modpart is None:
                        for cc in mod_node.children:
                            if cc.type == 'dotted_name':
                                modpart = cc
                                break
                    if modpart is not None:
                        module = '.'.join(_dotted(modpart) or [])
                else:
                    parts = _dotted(mod_node)
                    if parts:
                        module = '.'.join(parts)
            line = _row(node)
            # For a relative import, resolve the leading dots against the
            # importing file's directory so the graph can link to the real
            # file (e.g. `from .. import b` in pkg/sub/leaf.py -> pkg/b).
            base = ''
            if level > 0:
                parts = relpath.replace('\\', '/').split('/')
                base = parts[:-1]
                base = base[:len(base) - (level - 1)]
                base = '/'.join(base)

            def eff(target):
                if level == 0 or not target:
                    return target
                if base:
                    return base + '/' + target
                return target

            # Only the symbols AFTER the `import` keyword are imported names;
            # the module path (a `dotted_name` child before `import`) must be
            # skipped, otherwise `from m import n` also emits a PHANTOM import
            # for `m` (bind=m, name=m) alongside the real one for n. (The
            # grammar gives the module a `module_name` field, but tree-sitter
            # returns fresh wrappers per access, so position — not identity —
            # is the reliable way to tell the two dotted_names apart.)
            children = list(node.children)
            import_idx = next((i for i, c in enumerate(children)
                               if c.type == 'import'), None)
            for i, c in enumerate(children):
                if import_idx is not None and i <= import_idx:
                    continue
                if c.type == 'dotted_name':
                    nm = '.'.join(_dotted(c) or [])
                    if not nm:
                        continue
                    target = eff(module) if module else eff(nm)
                    note_import(target, line, bind=nm, name=nm, level=level)
                elif c.type == 'aliased_import':
                    tgt = c.child_by_field_name('name')
                    al = c.child_by_field_name('alias')
                    tp = _dotted(tgt) if tgt is not None else None
                    if not tp:
                        continue
                    name = '.'.join(tp)
                    bind = _text(al) if al is not None else name
                    target = eff(module) if module else eff(name)
                    note_import(target, line, bind=bind, name=name, level=level)
                elif c.type == 'wildcard_import':
                    target = eff(module) if module else (base if level else None)
                    if target:
                        note_import(target, line, bind='*', name=None,
                                    level=level)
            return

        if t == 'class_definition':
            # Record the class as a resolvable symbol: constructor calls
            # (`Body(...)`) must bind through the caller's imports instead
            # of falling through to `external`.
            nm = node.child_by_field_name('name')
            cname = _text(nm) if nm is not None else None
            if cname is not None:
                row = _row(node)
                key = (cname, row)
                if key not in seen_cls:
                    seen_cls.add(key)
                    classes.append({'name': cname,
                                    'qualified': '.'.join(qual + (cname,))
                                    if qual else cname,
                                    'line': row,
                                    'end_line': node.end_point[0] + 1})
            # Base classes may contain calls (`class Foo(Base())`); walk them
            # in the current scope.
            sup = node.child_by_field_name('superclasses')
            if sup is not None:
                walk(sup, depth, qual)
            # The body is a nested scope: walk it at depth+1 so class
            # attributes are NOT recorded as module-level file_vars, and push
            # the class name so methods get qualified names (``Vec3.normalize``).
            body = node.child_by_field_name('body')
            if body is not None:
                q = qual + (cname,) if cname is not None else qual
                walk(body, depth + 1, q)
            return

        for c in node.children:
            walk(c, depth, qual)

    walk(root, 0)
    return {'functions': fns, 'file_vars': file_vars,
            'calls': calls, 'imports': imports, 'classes': classes}


def module_candidates(module, relpath):
    """File paths a Python import of ``module`` could resolve to.

    Python packages use ``__init__.py`` (double underscore), so both the
    plain ``<path>.py`` and the ``<path>/__init__.py`` forms are offered —
    unlike the generic helper, which emits ``init.py`` and would never match
    a package root. (A relative import arrives here already resolved to a
    slashed path by the extractor.)"""
    slashed = module.replace('.', '/')
    return [f'{slashed}.py', f'{slashed}/__init__.py']


# ---------------------------------------------------------------------
# Self-test protocol (kodama-docs `test-backend python`)
#
# The source of truth is what CPython actually does with this fixture, not
# hand-written expectations:
#   * ``collect_truth()`` runs the fixture and records every call site and
#     import binding the runtime resolved (resolvable call sites + bindings);
#   * ``parse_markers()`` reads the fixture's ``# expect: ...`` lines, which
#     pin the deliberately unresolvable cases the runtime cannot reach.
# The generic harness (kodama_docs/testing.py) extracts the fixture with
# ``extract`` above, builds the kodama-docs graph, and checks it against
# these two sources.
# ---------------------------------------------------------------------

TEST_CODEBASE_DIR = Path(__file__).parent / 'test_codebase'

_MARKER_RE = re.compile(r'#\s*expect:\s*([A-Za-z][A-Za-z-]*)\s*(.*?)\s*$')

_KNOWN_KINDS = {
    'resolved', 'inferred', 'external', 'ambiguous', 'builtin',
    'import', 'import-unresolved',
}


def collect_truth():
    """Run the fixture's ``generate_truth.py`` and return its JSON dict.

    The fixture self-reports: it imports every executable module (with the
    fixture dir as ``sys.path[0]`` so project modules shadow stdlib) and
    records the call sites / bindings that actually resolved at runtime.
    Raises ``RuntimeError`` with the generator's stderr on failure — a broken
    fixture must fail loudly, never silently pass."""
    gen = TEST_CODEBASE_DIR / 'generate_truth.py'
    r = subprocess.run(
        [sys.executable, str(gen)],
        capture_output=True, text=True,
        cwd=str(TEST_CODEBASE_DIR), timeout=120)
    if r.returncode != 0:
        raise RuntimeError(
            'truth generator failed (exit %d):\n%s'
            % (r.returncode, (r.stderr or r.stdout).strip()))
    return json.loads(r.stdout)


def parse_markers(source):
    """Return the fixture's expectation markers in one source file.

    Grammar (same-line ``# expect:`` comment):
        # expect: resolved <file>::<name>
        # expect: inferred <file>::<name>
        # expect: external <label> [<label> ...]
        # expect: ambiguous
        # expect: builtin <label>
        # expect: import-unresolved
    Each marker is ``{'line', 'kind', 'targets'}`` where ``targets`` is the
    list of expected labels (empty for ``ambiguous`` / ``import-unresolved``).
    """
    out = []
    for i, line in enumerate(source.splitlines(), 1):
        m = _MARKER_RE.search(line)
        if not m:
            continue
        kind = m.group(1)
        if kind not in _KNOWN_KINDS:
            continue
        rest = m.group(2)
        targets = rest.split() if rest else []
        out.append({'line': i, 'kind': kind, 'targets': targets})
    return out


def _selftest_protocol_complete():
    """True when this backend implements the full self-test contract."""
    return all(hasattr(globals(), a)
               for a in ('TEST_CODEBASE_DIR', 'collect_truth',
                         'parse_markers'))
