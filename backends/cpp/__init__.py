"""C / C++ / CUDA extraction backend (tree-sitter based).

Parsing is delegated to the official tree-sitter-cpp grammar for C and C++,
and to tree-sitter-cuda for ``.cu`` / ``.cuh`` files. The package projects a
concrete syntax tree into the neutral shape documented in
``backends/backend_design.md``; no hand-rolled tokenizer or parser.

Layout:
    constants.py   language family, CUDA extensions, class/identifier sets
    builtins.py    standard-library/CUDA names that are not project links
    parser.py      parser selection and c/cpp/cuda dialect detection
    comments.py    comment marker cleaning (developer comments)
    nodes.py       name/declarator/parameter helpers over tree-sitter nodes
    values.py      variable/macro value classification + include guards
    calls.py       callee and receiver extraction
    includes.py    quoted #include resolution candidates
    pybind.py      explicit pybind11 exports (EXPORTS/BRIDGES facts)
    extract.py     the walk that produces the backend records

Policy decisions (kept intentionally simple and deterministic):

* **Definitions, not prototypes.** A header prototype is not a symbol
  record; the definition in the ``.c`` / ``.cpp`` file is. Header-only,
  inline and template definitions are still recorded.
* **Function-like macros are functions.** They carry their parameters so
  C APIs built on macros stay visible. Object-like macros are file vars.
* **Qualified names are dotted.** ``ns::Engine::step`` becomes
  ``ns.Engine.step``.
* **Quoted includes only.** Angle-bracket system headers are skipped so they
  do not become thousands of unresolved module nodes.
* **CUDA kernel launches are calls.** ``k<<<grid, block>>>(args)`` is a
  normal ``call_expression`` in tree-sitter-cuda.

Known limitations: tree-sitter is syntactic, so overload resolution, macro
expansion, template instantiation and include-directory resolution are best
effort. Calls are resolved by the graph's name/qualified-name heuristics,
never guessed here.
"""

from .builtins import BUILTIN_NAMES
from .constants import LANG
from .extract import extract
from .includes import module_candidates

__all__ = ['BUILTIN_NAMES', 'LANG', 'extract', 'module_candidates']
