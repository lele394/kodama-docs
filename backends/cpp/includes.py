"""Quoted ``#include`` handling for the C-family backend."""
import os

from .nodes import node_text


def include_module(node):
    """The path of a quoted include, or None for a system ``<...>`` include."""
    path = node.child_by_field_name('path')
    if path is None or path.type != 'string_literal':
        return None
    raw = node_text(path).strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    return None


def module_candidates(module, relpath):
    """Relpaths a quoted ``#include`` could resolve to.

    Tries the including file's directory first (the C/C++ convention), then
    the source root, then a common ``include/`` prefix. The graph picks the
    first candidate that is a real project file; unresolved includes stay
    visible as ``mod:...`` nodes.
    """
    m = str(module or '').replace('\\', '/').strip()
    if not m or m.startswith('<'):
        return []
    d = os.path.dirname(str(relpath).replace('\\', '/'))
    out = []
    for base in (d, ''):
        p = os.path.normpath(os.path.join(base, m)).replace('\\', '/')
        while p.startswith('./'):
            p = p[2:]
        if p and p not in out:
            out.append(p)
    extra = os.path.normpath(os.path.join('include', m)).replace('\\', '/')
    if extra not in out:
        out.append(extra)
    return out
