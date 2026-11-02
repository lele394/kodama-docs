"""Python extraction backend (tree-sitter based).

The package projects a tree-sitter-python concrete syntax tree into the
neutral shape documented in ``backends/backend_design.md``. No hand-rolled
tokenizer/parser.

Layout:
    constants.py   language tag and parameter node types
    builtins.py    Python builtins/stdlib names (not project links)
    parser.py      the parser instance
    comments.py    '#' comment cleaning
    nodes.py       names/receivers/params/value helpers
    includes.py    import resolution candidates
    extract.py     the walk that produces the backend records
    selftest.py    ``test-backend python`` fixture protocol

Record shapes (1-based lines, identical to the Lua backend):
    functions: [{id, name, qualified, line, end_line, params, vararg, body,
                 developer_comment: str|None, skip_llm?: bool}]
    file_vars: [{name, line, init, developer_comment, skip_llm?}]
    calls:     [{callee, line, method: str|None}]
    imports:   [{module, line, bind?: str, name?: str, level?: int}]
        -- `bind` is the local name an import binds; `name` is the target
        symbol for a from-import; `level` is relative-import depth.
    classes:   [{name, qualified, line, end_line, developer_comment,
                 skip_llm?}]
"""

from .builtins import BUILTIN_NAMES
from .constants import LANG
from .extract import extract
from .includes import module_candidates
from .selftest import TEST_CODEBASE_DIR, collect_truth, parse_markers

__all__ = [
    'BUILTIN_NAMES',
    'LANG',
    'TEST_CODEBASE_DIR',
    'collect_truth',
    'extract',
    'module_candidates',
    'parse_markers',
]
