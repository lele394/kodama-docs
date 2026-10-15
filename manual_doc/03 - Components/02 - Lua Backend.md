# Lua backend

`backends/lua/` — the Lua backend (manifest name `kodama-lua`). Parsing is delegated to the official **tree-sitter-lua** grammar; the module only walks the concrete syntax tree and projects it into the [record contract](../02%20-%20How%20It%20Works/03%20-%20Extraction.md). There is no hand-rolled tokenizer.

## What it extracts

| Construct | How it appears in the record |
| --- | --- |
| `function foo(...)`, `local function bar(...)`, `A:method(...)`, `A.b = function ...` | `functions` — `name`, `qualified` (dotted path, e.g. `A.method`), 1-based `line`/`end_line`, `params`, `vararg`, the exact source `body`, and a `developer_comment` when a comment block sits directly above the definition. |
| `local X = ...` / `X = ...` at file scope | `file_vars` — `name`, `line`, `init` form (`empty` / `table` / `string` / `number` / `function` / `call` / `expr`); for `local A = require('mod')` / `dofile('path')` a `module` field is added, which is what lets the graph resolve `A:method()` to that module's method. |
| `f(x)`, `A.b(x)`, `x:m(x)` | `calls` — `callee` plus, for a method call, the object part as `callee` and the method name as `method`. Computed receivers (`foo()()`) come out as `callee: null`. |
| `require('m')`, `dofile('p')` | `imports` — the module string and its line. |
| `local h = function ...`, `{ key = function ... }`, `foo(function ...)` | `functions` too — closures are named from their context (the declared name, the table field key, or the callee they're passed to); if none applies they are recorded as `anon`. |

## Lua-specific behavior

- **Method calls** use the colon form (`x:m`), so the caller side splits `m` into `method` and the object into `callee`; the resolver then matches against the method name in the target file (e.g. `Body:new()` → `new` in the module that defines it).
- **`BUILTIN_NAMES`** lists the Lua standard globals and libraries (`print`, `pairs`, `table`, `math`, `io`, …) so the resolver classifies them as `builtin` calls instead of unresolved project references.
- **`self` / `_G` / `_VERSION`** are treated as builtin names, and a definition written as `A:method` is only recognized as a method when its first parameter is `self` — keeping `A.x = function(self)` honest.
- **Closures get context names.** `local h = function … end` → `h`; a table field `{ handler = function … end }` → `handler`; a closure passed to a call → the callee's base name. A closure with no such context is recorded as `anon` — it still appears in the graph and on the page, but the LLM phase skips `anon` functions unless `documentation.include_anonymous_functions` is set (default `false`).

## Requirements and self-test

- python: `tree-sitter==0.26.0`, `tree-sitter-lua==0.5.0` (declared in the manifest; `--list-backends` shows them and `--install` pip-installs them for a new backend).
- The Lua backend does **not** implement the self-test protocol (`TEST_CODEBASE_DIR` / `collect_truth` / `parse_markers`) yet, so `test-backend --backend lua` reports that. Its behavior is covered by the same generic graph harness that the [Python backend](03%20-%20Python%20Backend.md) uses.

Related: [Backends](01%20-%20Backends.md), [Symbols and Graph](../07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md).
