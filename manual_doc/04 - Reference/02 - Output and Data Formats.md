# Output and Data Formats

A run produces two families of artifacts: the **human-readable docs** under `output_dir`, and the **machine data** (analysis cache, LLM records, graph, diagnostics) under `data_dir`. This page lists every file, its location, its exact on-disk shape, and which component writes it.

## Output directory (`output_dir`)

| Path | Writer | What it is |
| --- | --- | --- |
| `index.md` | render | the index: `# Documentation index`, a "Manual documentation" nested bullet list mirroring the manual's folder hierarchy (if `manual_doc` is set), the "N files documented." line, a per-file table (File / Lines / Functions / Variables), and an "Analysis summary" section. |
| `files/<relpath>.md` | render | one page per source file (see [Rendering](../02%20-%20How%20It%20Works/07%20-%20Rendering.md) for the exact page layout). |
| `manual/…` | manual copy | a verbatim copy of the configured `manual_doc` folder (all files, so relative images/links work), plus `manual/` entries surfaced on the index. |
| `meta/graph.json` | render (when `copy_meta`) | copy of the graph for the web graph view. |
| `meta/symbols.json` | render (when `copy_meta`) | copy of the analysis cache. |
| `meta/diagnostics.json` | render (when `copy_meta`) | copy of the diagnostics. |
| `.doc_cache` | outputs | `{"schema": "kodama_docs/doc_cache@1", "files": {relpath: md5}}` — the dirty/stale tracker (see [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md)). |

## Data directory (`data_dir`)

| Path | Writer | What it is |
| --- | --- | --- |
| `symbols.json` | scan | the per-file analysis cache. `{"schema": "kodama_docs/symbols@1", fingerprint, file_count, backends: {".lua": "kodama-lua@0.1.0", …}, files: […]}`. Each `files[]` entry carries `relpath`, `lines`, `size`, `status`, plus the extracted `functions` / `file_vars` / `calls` / `imports` / `classes`. The `backends` stamp is `active_backend_ids()` — if a backend's `name@version` for a given extension changes, the whole analysis is invalidated (a backend upgrade forces re-extraction). |
| `graph.json` | graph | the call/reference graph in **networkx node-link format** (`edges='edges'`, multigraph). Nodes carry `id` and `kind` (`file` / `class` / `function` / `variable` / `module` / `builtin` / `external`); edges carry `relation` (`CONTAINS` / `CALLS` / `IMPORTS` / `READS`) and, for `CALLS`, a `status` (`resolved` / `inferred` / `builtin` / `external` / `unresolved`). |
| `diagnostics.json` | scan | `{"schema": "kodama_docs/diagnostics@1", …}` — see below. |
| `functions/*.json` | LLM phase | one record per function (see [Records](#records)). |
| `variables/*.json` | LLM phase | one record per file-level variable. |
| `summaries/*.json` | LLM phase | one record per file summary. |
| `chunks/*.json` | LLM phase | one record per chunk of a long function. |

### Records

One JSON file per task, under the kind's subdirectory, named `{kind}_{md5(relpath)[:10]}_{sanitized_name}_{line}.json`. Shape:

```json
{
  "schema": "kodama_docs/record@1",
  "kind": "function",                 // function | variable | summary | chunk
  "file": "src/foo.lua",
  "name": "do_thing",
  "line": 42,
  "symbol": { …the symbol this prose was generated for… },
  "prose": { …the generated fields, per the kind's schema… },
  "fingerprint": "<sha256>",
  "stubbed": true                     // only for --no-llm placeholder prose
}
```

- **`fingerprint`** is the invalidation key: it folds in the symbol's source, its callers/callees, the settings that shaped its prompt, and the model. A mismatch is a cache miss (see [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md)).
- **`stubbed: true`** marks `--no-llm` placeholder prose. A full run treats stub records as misses and overwrites them; `--no-llm` runs may reuse them.

### `diagnostics.json` (detail)

```json
{
  "schema": "kodama_docs/diagnostics@1",
  "fingerprint": "<scan fingerprint>",
  "resolution_success": {
    "calls":  { "success": 1619, "failed": 1286 },
    "imports": { "success": 51,   "failed": 162 },
    "reads":  { "success": 60,   "failed": 0 }
  },
  "analysis": {
    "counts": { "ok": 89, "failed": 0, "binary": 0 },
    "files": { "<relpath>": { "status": "ok" } }
  },
  "graph": {
    "ambiguous_calls": [ {"file": "a/lua.lua", "line": 10, "name": "add",
                          "candidates": ["x/vec3.lua::add@10", "y/vec3.py::add@21"]} ],
    "inferred_calls":  [ {"file": "a/lua.lua", "line": 40, "name": "helper"} ],
    "external_calls":  [ {"file": "a/lua.lua", "line": 20, "name": "print"} ],
    "builtin_calls":   [ {"file": "a/lua.lua", "line": 5, "name": "pairs"} ],
    "unresolved_imports": [ {"file": "a/lua.lua", "line": 1, "module": "mod"} ]
  }
}
```

The `graph.*` values are **sorted lists of diagnostic objects** (not counts) — each entry names the file, line, and the call/involved symbol (ambiguous calls also carry their `candidates`), so a reviewer can jump straight to the site. These lists feed the index's "Analysis summary" and the "Call references: … external, … inferred, … ambiguous, … unresolved" line (which shows their lengths).

## Related

- [Rendering](../02%20-%20How%20It%20Works/07%20-%20Rendering.md) — the exact markdown page layout.
- [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md) — how the fingerprints and `.doc_cache` interact.
- [Symbols and Graph](../07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md) — node/edge semantics.
- [Glossary](../07%20-%20Concepts/02%20-%20Glossary.md).
