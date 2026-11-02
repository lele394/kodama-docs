# C/C++/CUDA backend

`backends/cpp/` — the C-family backend (manifest name `kodama-cpp`). It claims
`.c`, `.h`, `.cc`, `.cpp`, `.cxx`, `.hh`, `.hpp`, `.hxx`, `.cu` and `.cuh`,
using **tree-sitter-cpp** for C/C++ and **tree-sitter-cuda** for CUDA.

`__init__.py` is a thin entrypoint; the implementation is split into
`constants.py`, `builtins.py`, `parser.py`, `comments.py`, `nodes.py`,
`values.py`, `calls.py`, `includes.py`, `pybind.py`, and `extract.py`.

## What it extracts

| Construct | How it appears in the record |
| --- | --- |
| `int f(...)`, `Engine::step(...)`, methods, constructors/destructors, operators | `functions` — `name`, dotted `qualified` (e.g. `mixed.Engine.step`), `line`/`end_line`, `params`, `vararg`, exact `body`, optional `developer_comment`. |
| `class` / `struct` / `union` | `classes` — `name`, dotted `qualified`, line range, developer comment. Forward declarations with no body are skipped. |
| globals and object-like macros | `file_vars` — `name`, `line`, `init`, optional `value`. Include guards are not treated as API variables. |
| `#define ADD(a, b) ...` | a function-like macro, with its parameters. |
| `#include "local.h"` | `imports` — quoted includes only; angle-bracket system headers are skipped. Resolution tries the including directory, the source root, then `include/`. |
| `f(x)`, `ns::f(x)`, `obj.method(x)`, `ptr->method(x)` | `calls` — dotted receiver plus method where applicable; `this->m()` is bound to the enclosing class. |
| `kernel<<<grid, block>>>(args)` | a normal call in the tree-sitter-cuda grammar, so kernel launches appear in the graph. |

Function prototypes in headers are not documented; the definition in the
`.c`/`.cpp` file is. Header-only inline and template definitions are recorded.

## pybind11 bridge

The backend reads explicit pybind11 declarations from `PYBIND11_MODULE`,
`m.def(...)`, and `py::class_<T>(m, "Name").def(...)`. Those become `bindings`
records; the graph turns them into:

- `EXPORTS` — binding file → C++ class/function/method
- `BRIDGES` — Python facade class → the C++ class it wraps

`mixed_native.Engine(...)` calls resolve exactly through the binding instead of
being guessed by name. ctypes/Cython/torch-extension boundaries are not
declarative and stay inferred/unresolved.

## Developer comments and LLM skips

The usual glue rule applies to functions, classes, globals and macros,
including multiline `/* ... */` blocks. If the first non-empty line of the
comment is `kodama-docs-llm:skip`, no LLM task is created for that symbol; a
class-level skip also covers its methods, constructors and nested classes.
See [Prompts](../04%20-%20Reference/03%20-%20Prompts.md) for the template keys.

## Requirements and limits

- python: `tree-sitter==0.26.0`, `tree-sitter-cpp==0.23.4`,
  `tree-sitter-cuda==0.21.2` (declared in the manifest).
- tree-sitter is syntactic: overload resolution, macro expansion, template
  instantiation and include directories are best-effort. The graph marks
  inferred and ambiguous links instead of guessing.
- The mixed fixture `test_codebases/mixed-c-cpp-cu-py/` exercises C, C++,
  CUDA and Python together, including the pybind11 bridge and skip directives.
  `tests/test_cpp_backend.py` covers extraction and graph behavior directly.

Related: [Backends](01%20-%20Backends.md), [Adding a Language](../08%20-%20Contributing/01%20-%20Adding%20a%20Language.md).
