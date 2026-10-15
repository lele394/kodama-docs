# Parsing and resolution

Two different things can go wrong here, and the tool reports them distinctly: **parsing** (a file couldn't be extracted into symbols) and **resolution** (a call/import couldn't be tied to a definition). Neither silently disappears — both are surfaced in the run log, `diagnostics.json`, and the rendered index.

## "no ready backend claims '.x' (see --list-backends)"

The file's extension has no backend claiming it. Check what's actually available:

```bash
python main.py --list-backends
```

Each backend shows a `status`:

| Status | Meaning | Fix |
| --- | --- | --- |
| `ready` | importable, claims its extension | — (this one is used) |
| `unavailable` | its tree-sitter grammar/dependency is missing or failed to import | `pip install -r requirements.txt` (or install the backend with `--install URL`), then re-check |
| `conflict` | two backends claimed the same name or extension — **both** are dropped | remove one (`--remove NAME`) or fix the duplication |
| `invalid` | the backend manifest is malformed | fix the backend |

Because files are routed by the extensions backends *claim* (not by a config list), a language simply cannot be documented until a backend for it is `ready`.

## "failed to analyze <file>: <error>"

A per-file parse/extraction exception. The run continues (per-file isolation is by design), the file is counted in `diagnostics.json` as `analysis.counts.failed`, and it is listed in the index's Analysis summary with its error. Binary-looking files are counted separately as `binary` ("no symbols extracted").

- **Lua closure surprises** — a closure is always recorded; it is named from its context (the declared variable, a table field key, or the callee's base name), falling back to `anon`. Anonymous functions still appear in the graph and rendered pages; only the LLM phase and the report counts exclude them by default (`documentation.include_anonymous_functions` is `false`). If you want `anon` functions documented too, set it to `true`.
- **Python decorators** — a decorated function's `line` is the *first decorator's* line, so a comment above `@decorator` is still captured as its doc comment. This is intentional, not a misparse.

If a file's symbols look stale after you edited it, the analysis cache is fingerprinted: changing source, or changing the backend's `name@version` for that extension, invalidates the cached extraction. Use `--fresh` to bypass the `symbols.json` cache entirely (see [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md)).

## Resolution outcomes (what the links mean)

The resolver classifies every call/import/reference. On a rendered page, and in `diagnostics.json`'s `graph` section, they appear as:

| Outcome | Page shows | Meaning / how to improve |
| --- | --- | --- |
| **resolved** | a real link to the definition | bound via an import (e.g. `local Body = require("physics.body")`) or an explicit import — the ideal case. |
| **inferred** | `name (inferred)` | the name is defined **exactly once** project-wide but wasn't import-bound (e.g. calling through a parameter of unknown type). Kept but not linked. Binding the receiver to a module (require/import) makes it resolve. |
| **ambiguous** | *nothing linked* — it goes to `graph.ambiguous_calls` (with its `candidates` list) | the name is defined **more than once**, so the tool refuses to guess. Rename one, or narrow the import so only one definition is in scope. |
| **external / builtin** | orange `<span>` (no link) | a stdlib/global name (`print`, `pairs`, `os.path`, …) — by design, not an error. |
| **unresolved import** | listed in `graph.unresolved_imports` | the imported module isn't part of the documented project (third-party or system). Expected for e.g. `log` in the Lua sample. |

These feed the index's "Call references: X external, Y inferred, Z ambiguous (recorded, not linked), U unresolved import(s)" line and the "Resolution: S/T call references and I/J imports resolved successfully" summary — so you can see, per project, how much of the graph actually resolved.

## Quick checklist

1. `python main.py --list-backends` → is the language `ready`?
2. Run log: any `! failed to analyze …` lines? (parsing)
3. `diagnostics.json` → `graph.ambiguous_calls` / `inferred_calls` / `unresolved_imports` (resolution).
4. Index "Analysis summary" → the same numbers, human-readable.
5. Still stuck? `--fresh` to force re-extraction; `--regenerate` to delete and rebuild everything.

Related: [Symbols and Graph](../07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md), [Glossary](../07%20-%20Concepts/02%20-%20Glossary.md), [Lua Backend](../03%20-%20Components/02%20-%20Lua%20Backend.md), [Python Backend](../03%20-%20Components/03%20-%20Python%20Backend.md).
