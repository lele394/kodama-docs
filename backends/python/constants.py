"""Shared constants for the Python backend."""

LANG = 'python'

#: Parameter node types that may hide the name one level down. Older
#: tree-sitter-python (<=0.20) used multiple_parameter / keyword_parameter /
#: list_splat_parameter; the 0.25 grammar renamed them to list_splat_pattern /
#: dictionary_splat_pattern. Both are accepted so the backend is stable
#: across grammar builds.
PARAM_TYPES = (
    'identifier', 'typed_parameter', 'default_parameter',
    'typed_default_parameter', 'multiple_parameter', 'keyword_parameter',
    'list_splat_parameter', 'list_splat_pattern',
    'dictionary_splat_pattern',
)
