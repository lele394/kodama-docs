"""Comment cleaning for C/C++/CUDA developer comments."""
import re

from .nodes import node_text


def comment_text(node):
    """Strip ``//``, ``/* */`` and leading ``*`` decorations."""
    t = node_text(node).strip()
    if t.startswith('//'):
        t = t[2:]
        t = t.lstrip('/!<')
        return t.strip()
    if t.startswith('/*'):
        t = t[2:].removesuffix('*/')
        t = t.lstrip('!<')
        out = []
        for line in t.splitlines():
            line = line.strip()
            line = re.sub(r'^\*\s?', '', line)
            out.append(line)
        return '\n'.join(out).strip()
    return t
