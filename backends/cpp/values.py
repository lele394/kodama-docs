"""Variable/macro value helpers for the C-family backend."""
import re

from .nodes import node_text

#: Common include-guard macro names (``FOO_H``, ``FOO_HPP``, ``__FOO_H__``).
#: They are file plumbing, not API constants, so they are not documented as
#: file variables — otherwise every header would create a pointless LLM task.
_GUARD_RE = re.compile(
    r'^_*[A-Z][A-Z0-9_]*_(H|HH|HPP|HXX|CUH|INCLUDED)_*$')


def is_include_guard(name, value_text):
    if not _GUARD_RE.match(name):
        return False
    return value_text.strip() in ('', '1', '1U', '1UL', '1ULL')


def classify_value(value):
    """Map a tree-sitter value node to the neutral ``init`` vocabulary."""
    if value is None:
        return 'empty'
    t = value.type
    if t in ('string_literal', 'raw_string_literal', 'concatenated_string'):
        return 'string'
    if t in ('number_literal', 'char_literal'):
        return 'number'
    if t in ('initializer_list', 'compound_literal_expression'):
        return 'table'
    if t in ('call_expression', 'new_expression'):
        return 'call'
    if t == 'lambda_expression':
        return 'function'
    return 'expr'


def value_text(value):
    if value is None:
        return None
    text = node_text(value).strip()
    return text[:400] if text else None
