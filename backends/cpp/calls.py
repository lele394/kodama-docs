"""Callee discovery for C/C++/CUDA call expressions."""

from .nodes import name_parts, node_text


def static_path(node):
    """Dotted path of a static receiver, or None when it is computed."""
    if node is None:
        return None
    t = node.type
    if t in ('identifier', 'this'):
        return node_text(node).strip() or None
    if t == 'qualified_identifier':
        parts, _abs = name_parts(node)
        return '.'.join(parts) if parts else None
    if t == 'field_expression':
        arg = node.child_by_field_name('argument')
        field = node.child_by_field_name('field')
        base = static_path(arg)
        fld = static_path(field) if field is not None else None
        if base and fld:
            return f'{base}.{fld}'
        return base or fld
    if t in ('template_function', 'template_method', 'template_type'):
        parts, _abs = name_parts(node)
        return '.'.join(parts) if parts else None
    if t in ('pointer_expression', 'parenthesized_expression',
             'subscript_expression', 'call_expression'):
        return None
    return None


def call_target(node):
    """(callee, method) for a call_expression, or (None, None) when dynamic."""
    fn = node.child_by_field_name('function')
    if fn is None:
        return None, None
    t = fn.type
    if t == 'identifier':
        return node_text(fn).strip() or None, None
    if t == 'field_expression':
        field = fn.child_by_field_name('field')
        arg = fn.child_by_field_name('argument')
        method = None
        if field is not None:
            if field.type in ('field_identifier', 'identifier'):
                method = node_text(field).strip()
            else:
                parts, _abs = name_parts(field)
                method = parts[-1] if parts else None
        receiver = static_path(arg)
        return receiver, method
    if t == 'qualified_identifier':
        parts, _abs = name_parts(fn)
        return ('.'.join(parts) if parts else None), None
    if t in ('template_function', 'template_method'):
        parts, _abs = name_parts(fn)
        return ('.'.join(parts) if parts else None), None
    # ``(*fp)(...)``, ``arr[i](...)`` and other computed callees: keep the
    # call visible as an external ``?`` reference rather than guessing.
    return None, None
