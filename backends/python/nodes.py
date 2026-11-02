"""Small helpers for reading names, receivers, parameters and values from
the tree-sitter Python concrete syntax tree."""

from .constants import PARAM_TYPES


def node_row(node):
    """1-based line of a node's first character."""
    return node.start_point[0] + 1


def node_text(node):
    return node.text.decode('utf-8')


def dotted_parts(node):
    """dotted_name / identifier / name -> ['a', 'b', 'c']; None otherwise.

    `name` is the tree-sitter-python 0.25 node for a plain identifier
    (e.g. the receiver of `obj.method()` or `math.sqrt()`). A
    `dotted_name` is split on its dots: this is robust across grammar
    builds where the `object`/`attribute` fields are absent, and yields the
    full path (`a.b.c` -> ['a', 'b', 'c']) so nested-package imports like
    `from physics.body import Body` resolve to the real module.
    """
    if node is None:
        return None
    if node.type in ('identifier', 'name'):
        t = node_text(node).strip()
        return [t] if t else None
    if node.type == 'dotted_name':
        parts = [p for p in node_text(node).split('.') if p]
        return parts or None
    return None


def dotted_path(node):
    """Full dotted path of a STATIC receiver, or None when computed at runtime.

    Handles identifier/name, dotted_name and nested attribute chains. A
    receiver that is a call, subscript, lambda, ... is dynamic: there is no
    static target, so this returns None (the call is still recorded and
    surfaced as an external ``?.method`` reference).
    """
    if node is None:
        return None
    t = node.type
    if t in ('identifier', 'name'):
        s = node_text(node).strip()
        return [s] if s else None
    if t == 'dotted_name':
        return [p for p in node_text(node).split('.') if p] or None
    if t == 'attribute':
        obj = node.child_by_field_name('object')
        if obj is None:
            for c in node.children:
                if c.type in ('attribute', 'identifier', 'name'):
                    obj = c
                    break
        base = dotted_path(obj)
        attr = node.child_by_field_name('attribute')
        if attr is None:
            # The attribute is the *last* identifier child (the receiver is
            # the first); a naive first-match would grab the receiver.
            attr = next((c for c in reversed(node.children)
                         if c.type in ('identifier', 'name')), None)
        if base is None or attr is None:
            return None
        a = node_text(attr).strip()
        return base + ([a] if a else [])
    return None


def function_params(node):
    """function_definition -> (params, vararg)."""
    params = node.child_by_field_name('parameters')
    if params is None:
        return [], False
    names, vararg = [], False
    for c in params.children:
        if c.type in PARAM_TYPES:
            ident = c if c.type == 'identifier' else None
            if ident is None:
                for cc in c.children:
                    if cc.type == 'identifier':
                        ident = cc
                        break
            if ident is not None:
                names.append(node_text(ident))
            # A variadic parameter starts with '*' (`*args` / `**kwargs`);
            # a mere '*' in a default value (`size=1024*1024`) must NOT
            # trigger it.
            if node_text(c).lstrip().startswith('*'):
                vararg = True
    return names, vararg


def classify_value(node):
    """Map a value node to the neutral ``init`` vocabulary."""
    if node is None:
        return 'empty'
    t = node.type
    if t in ('dictionary', 'list', 'set', 'list_display', 'set_display',
             'tuple'):
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
