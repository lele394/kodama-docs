"""pybind11 export extraction.

A pybind11 module is the one place where a Python name is explicitly declared
to be a C++ symbol. Reading those declarations is deterministic (no guessing):
the backend records them, and ``graph.py`` turns them into EXPORTS/BRIDGES
edges and resolves ``mixed_native.Engine``-style calls.
"""

from .nodes import find_function_declarator, name_parts, node_row, node_text

_BINDING_MODULE_MACROS = {'PYBIND11_MODULE', 'PYBIND11_EMBEDDED_MODULE'}
_PYBIND_DEF_FIELDS = {
    'def', 'def_static', 'def_readwrite', 'def_readonly',
    'def_property', 'def_property_readonly', 'def_property_readonly_static',
}


def _walk_nodes(node, types):
    """Yield descendants of ``node`` whose type is in ``types``."""
    if node.type in types:
        yield node
    for c in node.children:
        yield from _walk_nodes(c, types)


def _function_name(node):
    fd = find_function_declarator(node.child_by_field_name('declarator'))
    if fd is None:
        return None
    parts, _abs = name_parts(fd.child_by_field_name('declarator'))
    return parts[-1] if parts else None


def _string_value(node):
    if node is None or node.type != 'string_literal':
        return None
    raw = node_text(node).strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    return None


def _cpp_ref(node):
    """C++ target of a pybind11 argument: ``&py_add`` / ``&ns::Engine::step``."""
    if node is None:
        return None
    if node.type == 'pointer_expression':
        return _cpp_ref(node.child_by_field_name('argument'))
    if node.type in ('identifier', 'qualified_identifier', 'template_function'):
        parts, _abs = name_parts(node)
        return '.'.join(parts) if parts else None
    if node.type == 'parenthesized_expression':
        for c in node.children:
            hit = _cpp_ref(c)
            if hit:
                return hit
    return None


def _binding_receiver(call):
    """Walk a chained ``.def(...)`` call down to its base receiver.

    ``m.def(...)`` -> the ``m`` identifier.
    ``py::class_<T>(m, "T").def(...).def(...)`` -> the ``py::class_`` call.
    """
    cur = call
    while True:
        fn = cur.child_by_field_name('function')
        if fn is None or fn.type != 'field_expression':
            return cur
        arg = fn.child_by_field_name('argument')
        if arg is None:
            return cur
        if arg.type != 'call_expression':
            return arg
        afn = arg.child_by_field_name('function')
        if afn is not None and afn.type == 'field_expression':
            fld = afn.child_by_field_name('field')
            if fld is not None and node_text(fld) in _PYBIND_DEF_FIELDS:
                cur = arg
                continue
        return arg


def _pybind_args(call):
    args = call.child_by_field_name('arguments')
    if args is None:
        return []
    return [c for c in args.children
            if c.type not in ('(', ')', ',')]


def _pybind_class_export(call):
    """(cpp_type, python_name) for ``py::class_<T>(m, "Name")``, else None."""
    fn = call.child_by_field_name('function')
    if fn is None or fn.type != 'qualified_identifier':
        return None
    name = fn.child_by_field_name('name')
    if name is None or name.type != 'template_function':
        return None
    base = name.child_by_field_name('name')
    if base is None or node_text(base) not in ('class_', 'struct_'):
        return None
    args = name.child_by_field_name('arguments')
    cpp_type = None
    if args is not None:
        for c in args.children:
            if c.type == 'type_descriptor':
                t = c.child_by_field_name('type')
                if t is None and c.children:
                    t = c.children[0]
                parts, _abs = name_parts(t)
                if parts:
                    cpp_type = '.'.join(parts)
                break
    py_name = None
    for a in _pybind_args(call):
        s = _string_value(a)
        if s:
            py_name = s
            break
    if cpp_type and py_name:
        return cpp_type, py_name
    return None


def _pybind_module_params(node):
    """(module name, module object) from ``PYBIND11_MODULE(name, m)``."""
    fd = find_function_declarator(node.child_by_field_name('declarator'))
    plist = fd.child_by_field_name('parameters') \
        if fd is not None else None
    if plist is None:
        return None, None
    vals = [node_text(c).strip() for c in plist.children
            if c.type in ('parameter_declaration',
                          'optional_parameter_declaration')]
    if len(vals) < 2:
        return None, None
    return vals[0].strip('"\''), vals[1]


def bindings(root, relpath):
    """Explicit pybind11 exports declared in this file."""
    out = []
    seen = set()

    def add(kind, module, name, target, line, owner=None):
        key = (kind, module, name, target, owner)
        if key in seen:
            return
        seen.add(key)
        rec = {'kind': kind, 'module': module, 'name': name,
               'target': target, 'line': line}
        if owner:
            rec['owner'] = owner
        out.append(rec)

    for fn_node in _walk_nodes(root, ('function_definition',)):
        if _function_name(fn_node) not in _BINDING_MODULE_MACROS:
            continue
        module, module_var = _pybind_module_params(fn_node)
        body = fn_node.child_by_field_name('body')
        if not module or not module_var or body is None:
            continue
        for call in _walk_nodes(body, ('call_expression',)):
            fn = call.child_by_field_name('function')
            if fn is None or fn.type != 'field_expression':
                continue
            fld = fn.child_by_field_name('field')
            if fld is None or node_text(fld) not in _PYBIND_DEF_FIELDS:
                continue
            args = _pybind_args(call)
            py_name = _string_value(args[0]) if args else None
            target = _cpp_ref(args[1]) if len(args) > 1 else None
            if not py_name or not target:
                continue
            base = _binding_receiver(call)
            cls = _pybind_class_export(base) \
                if base.type == 'call_expression' else None
            def_line = node_row(fld)
            if cls is not None:
                cpp_type, py_cls = cls
                add('class', module, py_cls, cpp_type,
                    base.start_point[0] + 1)
                add('method', module, py_name, target,
                    def_line, owner=py_cls)
            elif base.type == 'identifier' and \
                    node_text(base).strip() == module_var:
                add('function', module, py_name, target, def_line)
    return out
