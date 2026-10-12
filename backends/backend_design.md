# Backend design standard

A backend is a module in this package that turns one source file into
kodama-docs's language-independent symbol shape. Everything upstream of it
(tree-sitter grammars) and downstream of it (graph, LLM prose, markdown,
web view) is language-agnostic and must not need to know which backend ran.

Reference implementations: `lua.py`, `python.py`.

## Responsibilities

A backend does exactly this:

1. Parse the source with its tree-sitter grammar (no hand-rolled
   tokenizer/parser; grammars live in `requirements.txt`).
2. Walk the concrete syntax tree once and project it into the record shape
   below.
3. Classify call targets (local / external / builtin) using the file's
   imports, locals, and its own `BUILTIN_NAMES`.

A backend does **not** do: naming conventions, graph building, prose,
markdown, cross-file resolution. Those read the shape and nothing else.

## Contract

```python
def extract(source: str, relpath: str) -> dict
```

Returns a dict with exactly these keys:

| key | shape |
| --- | --- |
| `functions` | `[{id, name, qualified, line, end_line, params, vararg, body, developer_comment}]` |
| `file_vars` | `[{name, line, init}]` — `init` ∈ `empty, table, string, number, function, call, expr` (Lua) / `empty, string, number, call, expr` (Python) |
| `calls` | `[{callee, line, method}]` — a method call splits into object `callee` + `method`; plain calls have `method: None` |
| `imports` | `[{module, line}]` |

plus a module-level `BUILTIN_NAMES: set[str]` of standard-library names
that `extract` treats as builtins.

Invariants (all backends):

- **Lines are 1-based**; `line` is the declaration's first line, `end_line`
  the last line of the definition (may equal `line`).
- **`body`** is the exact source slice `lines[line-1 : end_line]` — the raw
  lines, never a grammar projection.
- **Document order**: `functions`, `calls`, `imports` appear in source
  order.
- **Determinism**: same input → same dict. No timestamps, no LLM, no
  global state between calls.
- **Per-file**: `extract` sees exactly one file. Cross-file questions
  (module candidates, what a name refers to) are answered by the pipeline,
  not the backend.
- **Tolerance**: a backend may skip constructs it cannot name (e.g.
  anonymous closures); it must not throw for them. `extract` throwing is
  caught per file by `main.analyze_files` (file fails, run continues).
- **Dedup**: a function node may appear in several grammar positions;
  backends dedup on the record `id` (`fn:{relpath}::{name}@{line}`).

### `developer_comment`

Each function record carries `developer_comment: str | None`: the cleaned
text of the comment block **glued** directly above the function, or `None`.

Glue rule (identical for every language):

- A comment node is *glued* to a function when its **last line is exactly
  the line above the function's first line** (no blank line or other code
  between them).
- The block is the **maximal run**: keep extending upward while the
  previous comment's last line sits exactly on the line above the current
  top.
- Any other content between comment and function (code, blank line) breaks
  the glue → `None`.

Implementation: use the shared helpers in `backends/__init__.py`
(`_all_comments(root)` for ordered comment nodes, `_dev_comment(comments,
fn_line, clean)` for the glue walk) and supply a per-language `clean(node)`
that strips the comment markers:

- **Lua**: the grammar's `comment` node has a `comment_content` child that
  already excludes `--` / `--[[ ... ]]`; strip whitespace.
- **Python**: each `comment` node is one `#` line; strip leading `#`+space
  with `re.sub(r'^\s*#+\s?', '', text).strip()`.

Docstrings / string literals are **not** comments and must never appear
here (they are `string` nodes, not `comment` nodes).

## Package-level duties (`backends/__init__.py`)

- `EXTRACTORS: {extension: extract}` — the dispatch table; `main.scan_files`
  filters on it, so a new extension is documented as soon as it is
  registered.
- `extract(source, relpath)` — public entry; raises `UnsupportedLanguage`
  for unknown extensions (caught per file upstream).
- `builtins_for(relpath)` — the backend's `BUILTIN_NAMES`, used by the
  graph builder to mark builtin nodes.
- `module_candidates(module, relpath)` — resolve a module reference from
  that language's file layout (Python: `mod.py`, `mod/__init__.py`,
  dotted→path; Lua: `mod.lua`, `mod/init.lua`, path variants). Used by
  the graph builder for module nodes — keep it pure (no file I/O).

## Adding a language

1. Add the grammar package to `requirements.txt` (tree-sitter +
   `tree_sitter_<lang>`).
2. Create `backends/<lang>.py` implementing the contract above, including
   `developer_comment` and `BUILTIN_NAMES`.
3. Register it in `backends/__init__.py`: the `.ext` in `EXTRACTORS`,
   `builtins_for`, and a `module_candidates` branch.
4. `settings.yaml` needs no change unless the project mixes extensions:
   `project.source_extensions` lists the extensions to scan (default: all
   registered).
5. Run with `--fresh` once: the analysis cache (`data/symbols.json`) is
   keyed on source hashes only, so existing cached extractions are reused
   until re-extraction is forced — this applies to backend **code**
   changes too, not just new languages.
