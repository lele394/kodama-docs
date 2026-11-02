"""Helpers for reading Lua names, calls, parameters and values from the
tree-sitter concrete syntax tree."""


def node_row(node):
    """1-based line of a node's first character."""
    return node.start_point[0] + 1


def node_text(node):
    return node.text.decode('utf-8')


def comment_text(node):
    """Cleaned comment text: the grammar's comment_content child, stripped
    (line `--` prefixes and `--[[ ... ]]` markers are not part of it)."""
    for c in node.children:
        if c.type == 'comment_content':
            return node_text(c).strip()
    return node_text(node).strip()


def ident(node):
    return node_text(node) if node is not None and \
        node.type == 'identifier' else None


def dotted(node, allow_method=False):
    """dot_index_expression -> ['a', 'b', 'c']; None if not a plain chain.

    With allow_method=True, a trailing method_index_expression (the colon
    form used in method definitions, e.g. `Body:new`) is also followed,
    with the method name becoming the last part.
    """
    parts = []
    while node is not None:
        if node.type == 'identifier':
            parts.insert(0, node_text(node))
            return parts
        if node.type == 'dot_index_expression':
            name = node.children[-1]
            if name.type != 'identifier':
                return None
            parts.insert(0, node_text(name))
            node = node.children[0]
            continue
        if allow_method and node.type == 'method_index_expression':
            method = node.child_by_field_name('method')
            if method is None or method.type != 'identifier':
                return None
            parts.insert(0, node_text(method))
            node = node.child_by_field_name('table')
            continue
        return None
    return None


def callee(node):
    """function_call -> (callee_name_or_None, method_name_or_None).

    A plain call `print(1)` -> ('print', None); a dotted call
    `A.b(1)` -> ('A.b', None); a method call `x:m(1)` -> ('x', 'm').
    """
    fn = node.child_by_field_name('name')
    if fn is None:
        return None, None
    if fn.type == 'identifier':
        return node_text(fn), None
    if fn.type == 'dot_index_expression':
        parts = dotted(fn)
        return ('.'.join(parts), None) if parts else (None, None)
    if fn.type == 'method_index_expression':
        method = ident(fn.child_by_field_name('method'))
        if not method:
            return None, None
        table = fn.child_by_field_name('table')
        if table is not None and table.type == 'identifier':
            return node_text(table), method
        parts = dotted(table) if table is not None else None
        if parts:
            return '.'.join(parts), method
        return None, method
    return None, None


def function_params(fn_node):
    """function_declaration/function_definition -> (params, vararg)."""
    params = fn_node.child_by_field_name('parameters')
    if params is None:
        return [], False
    names, vararg = [], False
    for c in params.children:
        if c.type == 'identifier':
            names.append(node_text(c))
        elif c.type == 'vararg_expression':
            vararg = True
    return names, vararg


def classify_value(node):
    """Map a value node to the neutral ``init`` vocabulary."""
    if node is None:
        return 'empty'
    t = node.type
    if t == 'table_constructor':
        return 'table'
    if t == 'string':
        return 'string'
    if t == 'number':
        return 'number'
    if t == 'function_definition':
        return 'function'
    if t == 'function_call':
        return 'call'
    return 'expr'


def var_names(var_list):
    """variable_list -> first declared name per target (identifier or the
    last part of a dotted target), in order."""
    names = []
    for c in var_list.children:
        if c.type == 'identifier':
            names.append(node_text(c))
        elif c.type == 'dot_index_expression':
            parts = dotted(c)
            names.append(parts[-1] if parts else None)
        else:
            names.append(None)
    return [n for n in names if n]


def string_value(node):
    for c in node.children:
        if c.type == 'string_content':
            return node_text(c).strip()
    return None


def require_module(node):
    """Module string if `node` is require('mod') / dofile('path'), else None."""
    if node is None or node.type != 'function_call':
        return None
    name, _method = callee(node)
    if not name or name.rsplit('.', 1)[-1] not in ('require', 'dofile'):
        return None
    args = node.child_by_field_name('arguments')
    if args is None:
        return None
    for c in args.children:
        if c.type == 'string':
            val = string_value(c)
            return val or None
    return None
