# Code organization

A map of the repository, so a change can be routed to the right file. (See [Adding a Language](01%20-%20Adding%20a%20Language.md) for the backend contract.)

## Top level

| Path | What it is |
| --- | --- |
| `main.py` | the CLI entry point. Parsers the flags (in precedence order: `--list-backends`/`--install`/`--remove`, `test-backend`, `--purge`/`--regenerate`, `--serve`, pipeline), then drives the four phases. See [CLI](../03%20-%20Components/06%20-%20CLI.md). |
| `settings.yaml` | the default config. All runtime configuration lives here (see [Config Reference](../04%20-%20Reference/01%20-%20Config%20Reference.md)). |
| `kodama_docs/` | the core Python package — the pipeline itself. |
| `backends/` | the language backends: `lua/`, `python/`, the shared `_shared.py`, the registry (`__init__.py`), and `backend_design.md` (the authoring contract). |
| `web/` | the `--serve` web app: `server.py` (routing), `render.py` (the deterministic markdown→HTML subset), the JS (`app.js`, `sidebar.js`, `graph.js`, `fuzzy.js`), `themes/`, and `web_settings.yaml`. |
| `prompts/` | the four LLM prompt files (see [Prompts](../04%20-%20Reference/03%20Prompts.md)). |
| `configs/` | example configs: `self.yaml` (dogfooding), `test.yaml`, `cloudcfg.yaml`. |
| `manual_doc/` | this manual (human-written; embedded into the generated docs via `manual_doc`). |
| `doc_self/`, `data_self/` | committed output of documenting kodama-docs itself (see [Documenting kodama-docs Itself](../05%20-%20Examples/02%20-%20Documenting%20kodama-docs%20Itself.md)). |
| `test_codebases/` | the small Lua and Python sample projects (N-body) used for end-to-end runs. |
| `tests/` | test suite: `test_manual.py`, `test_resolver.py`, `test_web_manual.py`. |
| `requirements.txt` | pinned dependencies. |
| `DESIGN.md` | the design notes. |
| `LICENSE` | MIT, plus an explicit "not for AI/ML training data" clause. |

## `kodama_docs/` — one module per phase

| Module | Responsibility |
| --- | --- |
| `config.py` | load `settings.yaml` + `.env` (project root first, then the config's directory); resolve the `llm` block. |
| `scan.py` | walk the tree, route files to backends, extract symbols, cache `symbols.json`, write `diagnostics.json`, report. |
| `graph.py` | build the resolution graph and the per-reference statuses (resolved/inferred/builtin/external/ambiguous) — see [Symbols and Graph](../07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md). |
| `context.py` | build the deterministic per-kind prompt context (function / variable / summary) and the chunk splitter. |
| `llm.py` | the `LLMClient` (transport + retries), `generate()` (validate + invalid-JSON retry), and the `--no-llm` stubs. |
| `llm_phase.py` | run the task queue over functions → variables → summaries, with the TUI. |
| `records.py` | save / load / delete the per-task LLM records and their fingerprints. |
| `models.py` | the per-kind JSON schemas and the deterministic validator (the same schemas embedded verbatim in prompts). |
| `markdown.py` | render `index.md` and the per-file pages (the deterministic structure + links). |
| `manual.py` | copy + surface a user-supplied `manual_doc` folder. |
| `outputs.py` | `--purge` / `--regenerate` dir handling and the `.doc_cache` write/check. |
| `tui.py` | the Rich terminal panel for the LLM phase. |
| `util.py` | small shared helpers (logging, id sanitizing, truncation). |

## How a change usually lands

- **Prose style / which fields** → the `prompts/` files (never the shape — that's `models.py`).
- **A link is wrong or missing** → `graph.py` resolution policy (and `BUILTIN_NAMES` / `module_candidates` in the relevant backend).
- **A page looks wrong** → `markdown.py` (render) or the LLM record (data), not the graph.
- **A cache seems stale** → `records.py` fingerprints or `.doc_cache` in `outputs.py`; see [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md).
- **A new language** → a new `backends/<lang>/` package; see [Adding a Language](01%20-%20Adding%20a%20Language.md).

## Conventions worth keeping

- **Determinism first** — structure, links, ordering, and line numbers are produced without the LLM; the model only supplies prose.
- **Per-file isolation** — one bad file never aborts the run; failures are reported, not raised.
- **Failures stay visible** — unresolved/ambiguous references are surfaced (orange, `(inferred)`, diagnostics), never silently dropped or guessed.
- **Stable keys** — node IDs (`fn:<relpath>::<name>@<line>`) and the `functions/file_vars/calls/imports/classes` record shapes are load-bearing for the cache and the graph; don't change them casually.

Related: [CLI](../03%20-%20Components/06%20-%20CLI.md), [How It Works: Overview](../02%20-%20How%20It%20Works/01%20-%20Overview.md).
