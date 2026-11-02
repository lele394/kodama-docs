"""Small helpers for reading names, declarators and parameters from the
tree-sitter C/C++/CUDA concrete syntax tree."""

from .constants import IDENT_TYPES


def node_row(node):
    """1-based line of a node's first character."""
    return node.start_point[0] + 1


def node_text(node):
    return node.text.decode('utf-8')


def same_node(a, b):
    """tree-sitter may hand out fresh wrappers for the same node — compare
    source ranges, not object identity."""
    return a is not None and b is not None and \
        a.start_byte == b.start_byte and a.end_byte == b.end_byte


def name_parts(node):
    """(path parts, absolute) for a name/declarator node.

    ``ns::Engine::run`` -> (('ns', 'Engine', 'run'), False);
    ``::foo`` -> (('foo',), True); ``foo`` -> (('foo',), False).
    """
    if node is None:
        return (), False
    t = node.type
    if t in IDENT_TYPES:
        s = node_text(node).strip()
        return ((s,) if s else ()), False
    if t in ('destructor_name', 'operator_name'):
        s = node_text(node).strip()
        return ((s,) if s else ()), False
    if t == 'nested_namespace_specifier':
        raw = node_text(node).replace('::', '.')
        return tuple(p for p in raw.split('.') if p), False
    if t == 'qualified_identifier':
        absolute = node_text(node).lstrip().startswith('::')
        scope = node.child_by_field_name('scope')
        name = node.child_by_field_name('name')
        sp = name_parts(scope)[0] if scope is not None else ()
        np = name_parts(name)[0] if name is not None else ()
        if not np:
            raw = node_text(node).replace('::', '.').strip('.')
            return tuple(p for p in raw.split('.') if p), absolute
        return tuple(sp) + tuple(np), absolute
    if t in ('template_function', 'template_method', 'template_type'):
        name = node.child_by_field_name('name')
        if name is not None:
            return name_parts(name)
        raw = node_text(node).split('<', 1)[0]
        return ((raw.strip(),) if raw.strip() else ()), False
    if t in ('pointer_declarator', 'reference_declarator',
             'parenthesized_declarator', 'function_declarator',
             'array_declarator', 'init_declarator'):
        d = node.child_by_field_name('declarator')
        if d is not None:
            return name_parts(d)
    for c in node.children:
        if c.type in IDENT_TYPES or c.type in ('destructor_name',
                                               'operator_name'):
            return name_parts(c)
    return (), False


def join_parts(qual, parts):
    """Prefix ``parts`` with the current lexical scope, without duplicating
    a scope the name already spells out (``mixed::Engine::run`` inside
    ``namespace mixed``)."""
    qual = tuple(p for p in qual if p)
    parts = tuple(p for p in parts if p)
    if not parts:
        return qual
    if qual and parts[:len(qual)] == qual:
        return parts
    return qual + parts


def definition_start_line(node):
    """Line where the definition starts, including a leading ``template``
    line so the body slice and developer-comment glue cover the whole
    construct."""
    while node.parent is not None and \
            node.parent.type == 'template_declaration':
        node = node.parent
    return node_row(node)


def find_function_declarator(node):
    if node is None:
        return None
    if node.type == 'function_declarator':
        return node
    for c in node.children:
        hit = find_function_declarator(c)
        if hit is not None:
            return hit
    return None


def declarator_name(node):
    """The identifier introduced by a declarator, descending through
    pointers/references/arrays/function-pointer parentheses."""
    if node is None:
        return None
    t = node.type
    if t in ('identifier', 'field_identifier', 'type_identifier'):
        return node_text(node).strip() or None
    if t in ('destructor_name', 'operator_name'):
        return node_text(node).strip() or None
    if t in ('pointer_declarator', 'reference_declarator',
             'array_declarator', 'parenthesized_declarator',
             'function_declarator', 'init_declarator',
             'attributed_declarator', 'parameter_pack'):
        d = node.child_by_field_name('declarator')
        if d is not None:
            return declarator_name(d)
        for c in node.children:
            name = declarator_name(c)
            if name:
                return name
    return None


def is_function_prototype(declarator):
    """True for ``int f(int);`` and false for a function-pointer variable
    ``int (*fp)(int);``."""
    if declarator is None or declarator.type != 'function_declarator':
        return False
    inner = declarator.child_by_field_name('declarator')
    return inner is not None and inner.type in (
        'identifier', 'field_identifier', 'qualified_identifier',
        'destructor_name', 'operator_name', 'template_function')


def function_params(fn_node):
    """(parameter names, vararg) for a function definition."""
    decl = find_function_declarator(
        fn_node.child_by_field_name('declarator'))
    plist = decl.child_by_field_name('parameters') \
        if decl is not None else None
    if plist is None:
        return [], False
    names, vararg = [], False
    for c in plist.children:
        if c.type == '...':
            vararg = True
            continue
        if c.type not in ('parameter_declaration',
                          'optional_parameter_declaration',
                          'variadic_parameter', 'parameter_pack'):
            continue
        if c.type == 'variadic_parameter':
            vararg = True
            continue
        name = declarator_name(c.child_by_field_name('declarator'))
        if name and name != 'void':
            names.append(name)
        # A parameter pack ``Ts...`` is variadic even without a ``...`` token.
        if node_text(c).rstrip().endswith('...'):
            vararg = True
    return names, vararg
