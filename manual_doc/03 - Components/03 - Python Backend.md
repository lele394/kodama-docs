# Python backend

`backends/python/` — the Python backend (manifest name `kodama-python`). Like the [Lua backend](02%20-%20Lua%20Backend.md) it delegates parsing to the official **tree-sitter-python** grammar and projects the tree into the [record contract](../02%20-%20How%20It%20Works/03%20-%20Extraction.md).

## What it extracts

| Construct | How it appears in the record |
| --- | --- |
| `def foo(...)`, `async def bar(...)`, class methods (`def m(self)`, `@staticmethod`, `@classmethod`) | `functions` — `name`, `qualified` (dotted path, e.g. `Outer.method`), 1-based `line`/`end_line`, `params`, `vararg`, exact `body`, optional `developer_comment` (a comment block directly above the definition). |
| module-level `X = ...` | `file_vars` — `name`, `line`, `init` form. Class attributes are **not** file vars — the contract forbids leaking `class A: X = 1` into the record. |
| `f(x)`, `A.b(x)`, `obj.m(x)`, `cls(x)` | `calls` — `callee` plus `method` for method-form calls; a computed receiver comes out as `callee: null`. |
| `import x as a`, `from m import n`, `from m import n as a`, `import a.b` | `imports` — `module`, `line`, `bind` (the local name: `a` / `n` / the module's last segment for a plain `import x`), `name` (the target symbol for a from-import), `level` for relative imports. |
| nested `def` inside a function | a separate function record per definition — the resolver disambiguates by scope, so a nested `def helper` and a module-level `helper` both exist, and each call site links to the one visible at its line. |

The import `bind`/`name` pair is what lets the graph resolve `a.method()` and bare `n()` to the imported module's definitions.

## Python-specific behavior

- **`BUILTIN_NAMES`** lists Python builtins *and* common stdlib modules (`os`, `sys`, `json`, `threading`, …) so the resolver classifies them as builtin rather than unresolved project references.
- **`module_candidates(module, relpath)`** overrides the generic guess: Python packages use `__init__.py` (double underscore), so both `<path>.py` and `<path>/__init__.py` are offered — the generic helper emits `init.py`, which would never match a package root.
- **Decorators shift the start line.** For a decorated function, `line` is the *first decorator's* line, so a comment above `@decorator` is still captured as the `developer_comment` (the exact-body invariant is kept: `body` spans `line..end_line`).

## Self-test

This backend implements the full self-test protocol, so

```bash
python main.py test-backend --backend python
```

runs its bundled fixture (`backends/python/test_codebase/`) through the real pipeline and checks the resulting graph against (a) what CPython actually resolves at runtime and (b) `# expect: ...` marker lines pinning the deliberately unresolvable cases — ambiguous names, external calls, unresolved imports, inferred calls. A green run is `249/249 passed` as of this writing. The harness is described in [Backends](01%20-%20Backends.md).

Related: [Backends](01%20-%20Backends.md), [Parsing and Resolution](../06%20-%20Troubleshooting/02%20-%20Parsing%20and%20Resolution.md).
