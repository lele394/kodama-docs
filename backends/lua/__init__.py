"""Lua extraction backend (tree-sitter based).

The package projects a tree-sitter-lua concrete syntax tree into the neutral
shape documented in ``backends/backend_design.md``. No hand-rolled parser.

Layout:
    constants.py   language tag
    builtins.py    Lua builtins/stdlib names (not project links)
    parser.py      the parser instance
    nodes.py       names/calls/params/value helpers
    extract.py     the walk that produces the backend records

Record shapes (1-based lines, stable across backends):
    functions: [{id, name, qualified, line, end_line, params, vararg, body,
                 developer_comment: str|None, skip_llm?: bool}]
    file_vars: [{name, line, init, developer_comment, skip_llm?,
                 module?: str}]
        -- `module` is present when the initializer is a module load
        -- (`local A = require('mod')` / dofile); it lets the graph phase
        -- resolve `A:method()` to that module's method.
    calls:     [{callee, line, method: str|None}]   (method call: callee is
                                                    the object part, method
                                                    the method name)
    imports:   [{module, line}]
"""

from .builtins import BUILTIN_NAMES
from .constants import LANG
from .extract import extract

__all__ = ['BUILTIN_NAMES', 'LANG', 'extract']
