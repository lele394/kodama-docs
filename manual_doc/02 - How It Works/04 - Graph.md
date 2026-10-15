# Graph

The records are joined into a single directed graph (a `networkx` graph, saved as `meta/graph.json`). The graph is the source of truth for every cross-link and for the interactive call-graph view.

## Nodes

| Kind | Encoded from | What it is |
| --- | --- | --- |
| file | file path | A source file. |
| function | file, name, line | A function or method. |
| variable | file, name, line | A file-level variable. |
| module | module name | A synthetic node for an import that could not be resolved to a file. |

## Edges

| Type | From | To | Resolved when |
| --- | --- | --- | --- |
| `CONTAINS` | file | function or variable | always |
| `CALLS` | function (or file) | function | the target exists in the documented set |
| `IMPORTS` | file | file (or module) | the module maps to a documented file |
| `READS` | function | variable | the variable is in the same file |

Every reference edge — `CALLS`, `IMPORTS`, `READS` — carries a `resolution_success` flag.

## Resolution and diagnostics

When a call or import cannot be resolved — an external function, a module that is not in the tree — it is still recorded, but as **unresolved**, and logged in `meta/diagnostics.json` under `unresolved_calls` / `unresolved_imports`. The renderers highlight these, so gaps stay visible instead of silent. The same file also records `inferred_calls` and `builtin_calls`, which resolved with lower confidence. See [Rendering](07%20-%20Rendering.md) and [Troubleshooting](../06%20-%20Troubleshooting/01%20-%20LLM%20Problems.md).

The node and edge model, and the resolution vocabulary, are defined in more depth in [Symbols and Graph](../07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md).
