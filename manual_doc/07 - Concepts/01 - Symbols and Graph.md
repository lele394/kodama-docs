# Symbols and Graph

kodama-docs builds one **directed multigraph** per project (a `networkx.MultiDiGraph`) from the extracted symbols. The graph is the single source of truth for the cross-references you see as links on the rendered pages. This page defines its vocabulary and the resolution policy that decides when a link is written.

## Nodes

Node IDs are deterministic strings; `kind` is a node attribute.

| Kind | ID shape | Example |
| --- | --- | --- |
| `file` | `file:<relpath>` | `file:src/main.lua` |
| `function` | `fn:<relpath>::<name>@<line>` | `fn:src/main.lua::tick@40` |
| `variable` | `var:<relpath>::<name>@<line>` | `var:src/main.lua::MODE@6` |
| `class` | `cls:<relpath>::<name>@<line>` | (backends that emit classes) |
| `module` | `mod:<name>` | `mod:physics.body` (from an import) |
| `builtin` | `builtin:<name>` | `builtin:print` |
| `external` | `ext:<name>` | `ext:os.path` |

`builtin:*` and `ext:*` are **synthetic** nodes — stand-ins so the docs can say "this is a stdlib call" or "this is outside the project" without guessing which file it lives in.

## Edges

| Type | Direction | Meaning |
| --- | --- | --- |
| `CONTAINS` | file → function / variable / class | the file defines the symbol. |
| `CALLS` | function (or file) → function / class / external / builtin | a call site. Carries `status` and `line`. |
| `IMPORTS` | file → file / module | the file imports a project module. Carries `resolved`/`unresolved` and `line`. |
| `READS` | function → variable | the function body references a file-level variable (only when that variable is defined in the project). |

Because the graph is a multigraph, **each call site keeps its own edge** — two calls to the same function from two lines produce two edges, each with its own `line`.

## The resolution policy (the important part)

For every `CALLS` edge the resolver decides a **status**, using the *caller file's* context in this fixed order:

1. **same file** — a function defined in the same file (lexical scope wins) → `resolved`.
2. **import-bound** — the caller's name bindings (`import x`, `from x import n`, `import x as a`, or Lua `local A = require('m')`) resolve to a project file that defines the target → `resolved`.
3. **builtin / stdlib** — a name in the caller language's builtin set → `builtin` (orange in the docs, no project link).
4. **inferred** — the name occurs **exactly once** across the whole project → `inferred`. This is a *documented inference*: the reference is kept and shown, but the docs can state it was inferred, not bound.
5. **ambiguous** — the name occurs **2+ times** in the project → **no edge is written at all**; the call site is recorded in diagnostics with its `candidates`. The tool refuses to guess.
6. **external** — anything else → `external` (kept as a synthetic node so the docs can say "unresolved").

**Ambiguity is never silently resolved by picking a candidate.** The documentation must be able to state what is known, what is inferred, and what is unresolved.

## What the renderer does with it

- `resolved` → a real link to the target's page/anchor.
- `inferred` → the name, suffixed `(inferred)`.
- `builtin` / `external` → an orange `<span>` (no link), with a note that it couldn't be resolved to a project symbol.
- The index's "Analysis summary" reports the counts: resolved vs ambiguous/inferred/external, and resolved vs unresolved imports.

See [Output and Data Formats](../04%20-%20Reference/02%20-%20Output%20and%20Data%20Formats.md) for the on-disk `graph.json` and `diagnostics.json` shapes, and [Parsing and Resolution](../06%20-%20Troubleshooting/02%20-%20Parsing%20and%20Resolution.md) for working through a specific ambiguous or unresolved reference.

Related: [Glossary](02%20-%20Glossary.md), [Rendering](../02%20-%20How%20It%20Works/07%20-%20Rendering.md).
