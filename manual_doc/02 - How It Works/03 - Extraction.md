# Extraction

Extraction is the step where a file becomes a structured **record**. Each file is handed to exactly one backend, and the backend returns a fixed, language-neutral shape that the rest of the pipeline depends on.

## The record contract

Every backend's `extract(source, relpath)` returns the same four top-level keys (plus one optional one):

| Key | Type | Meaning |
| --- | --- | --- |
| `functions` | list | Functions defined in the file: `name`, `qualified`, `line`, `end_line`, `params`, `vararg`, the exact source `body`, an optional `developer_comment`, and a stable `id`. |
| `file_vars` | list | File-level variables: `name`, `line`, and an `init` form (`empty`/`table`/`string`/`number`/`function`/`call`/`expr`). |
| `calls` | list | Call sites: `callee` (possibly dotted, or `None` for a computed receiver), `line`, and (for methods) `method`. |
| `imports` | list | Import statements: `module`, `line`, `bind`, `name`, and `level` (relative-import depth). |
| `classes` | list (optional) | Class definitions: `name`, `qualified`, `line`, `end_line`. Absent in languages without classes. |

Line numbers are 1-based and point into the same `source` string that was passed in; `body` must be exactly the source lines from `line` to `end_line`. Backends may add language-specific extras on top of these, but these keys are the contract. The graph and the renderers only ever read this shape, which is what lets a new language drop in without touching the pipeline. Optional extras include `lang`/`dialect`, `developer_comment` + `skip_llm` on symbols, and `bindings` (explicit cross-language exports such as pybind11). The full contract, with the invariants the pipeline relies on, is in `backends/backend_design.md` in the repository.

## How files are routed

At scan time each file's extension is matched to a backend by the registry. A file with no ready backend, or one that is excluded or too large, is skipped and reported rather than fatal — an unavailable or conflicted backend degrades gracefully, and `--list-backends` explains why.

## Where the backends live

- `backends/lua/` — the Lua backend (tree-sitter).
- `backends/python/` — the Python backend (tree-sitter).
- `backends/cpp/` — the C/C++/CUDA backend (tree-sitter-cpp + tree-sitter-cuda).
- `backends/_shared.py` — comment-glue/directive helpers shared by all.
- `backends/backend_design.md` — the contract for backend authors.

Each backend package keeps `__init__.py` as a thin entrypoint and splits the
implementation into modules (`extract.py`, `nodes.py`, `builtins.py`, …).

The general model is in [Backends](../03%20-%20Components/01%20-%20Backends.md);
the [Lua](../03%20-%20Components/02%20-%20Lua%20Backend.md),
[Python](../03%20-%20Components/03%20-%20Python%20Backend.md) and
[C/C++/CUDA](../03%20-%20Components/03b%20-%20C%20C%2B%2B%20CUDA%20Backend.md)
backends each get their own page.
