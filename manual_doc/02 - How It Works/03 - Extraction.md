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

Line numbers are 1-based and point into the same `source` string that was passed in; `body` must be exactly the source lines from `line` to `end_line`. Backends may add language-specific extras on top of these, but these keys are the contract. The graph and the renderers only ever read this shape, which is what lets a new language drop in without touching the pipeline. The full contract, with the invariants the pipeline relies on, is in `backends/backend_design.md` in the repository.

## How files are routed

At scan time each file's extension is matched to a backend by the registry. A file with no ready backend, or one that is excluded or too large, is skipped and reported rather than fatal — an unavailable or conflicted backend degrades gracefully, and `--list-backends` explains why.

## Where the backends live

- `backends/lua/` — the Lua backend (tree-sitter).
- `backends/python/` — the Python backend (tree-sitter).
- `backends/_shared.py` — helpers shared by both.
- `backends/backend_design.md` — the contract for backend authors (in the repository).

The general model is in [Backends](../03%20-%20Components/01%20-%20Backends.md); the Lua and Python backends each get their own page.
