"""Shared constants for the C / C++ / CUDA backend."""

#: Shared by C, C++ and CUDA so the graph may link across the C family
#: (a C++ file calling a C function is a real edge). ``dialect`` keeps the
#: finer distinction for display/diagnostics.
LANG = 'c-family'

CUDA_EXTS = ('.cu', '.cuh')

#: Node types that can carry a plain symbol name.
IDENT_TYPES = {
    'identifier', 'field_identifier', 'namespace_identifier',
    'type_identifier', 'statement_identifier',
}

#: Class-like definitions (all are recorded as ``classes``).
CLASS_TYPES = ('class_specifier', 'struct_specifier', 'union_specifier')
