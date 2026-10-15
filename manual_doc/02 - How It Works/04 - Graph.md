# Graph

The records are joined into a single directed graph (a `networkx` MultiDiGraph). It is saved as `<data_dir>/graph.json`, and — when `project.copy_meta` is set — copied to `meta/graph.json` in the output folder. The graph is the source of truth for every cross-link and for the interactive call-graph view served at `/graph`.

## Nodes

| Kind | Node id | What it is |
| --- | --- | --- |
| `file` | `file:<relpath>` | A source file. |
| `class` | `cls:<relpath>::<name>@<line>` | A class definition (recorded by backends that report classes). |
| `function` | `fn:<relpath>::<name>@<line>` | A function or method. |
| `variable` | `var:<relpath>::<name>@<line>` | A file-level variable. |
| `module` | `mod:<module>` | Synthetic: an import that could not be resolved to a documented file. |
| `builtin` | `builtin:<name>` | Synthetic: a call to a language/stdlib builtin, so it never dangles. |
| `external` | `ext:<name>` | Synthetic: a call the resolver could not place in the project. |

## Edges

| Type | From | To | Resolved when |
| --- | --- | --- | --- |
| `CONTAINS` | file | function, variable, or class | always |
| `CALLS` | function (or file) | function, class (constructor), builtin, or external | the target exists in the documented set |
| `IMPORTS` | file | file, or module | the module maps to a documented file |
| `READS` | function | variable | the variable is in the same file |

Every reference edge — `CALLS`, `IMPORTS`, `READS` — carries a `status` (`resolved` / `inferred` / `builtin` / `external` / `unresolved`) and a `resolution_success` flag; only `resolved`, `inferred`, and `builtin` count as successful.

## Resolution and diagnostics

Unresolvable references are not dropped — they are **recorded**. Each file's diagnostics are collected in `diagnostics.json` (in the data directory, and copied to `meta/` with `copy_meta` set) under five keys:

- `ambiguous_calls` — the name matched 2+ candidates, so no edge is drawn (the candidates are listed);
- `external_calls` — the name resolved to nothing in the project (a synthetic `ext:` node);
- `builtin_calls` — a language builtin or stdlib call (a synthetic `builtin:` node);
- `unresolved_imports` — a module that maps to no documented file (a `module` node);
- `inferred_calls` — resolved with lower confidence: the name is unique project-wide but not bound by a visible import, so the resolver *infers* the target (flagged as such on the edge).

The renderers highlight unresolved references, so gaps stay visible instead of silent. See [Rendering](07%20-%20Rendering.md) and [Parsing and Resolution](../06%20-%20Troubleshooting/02%20-%20Parsing%20and%20Resolution.md).

The node and edge model, and the resolution vocabulary, are defined in more depth in [Symbols and Graph](../07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md).
