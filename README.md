# doc_maker

Deterministic documentation generator for codebases.

doc_maker extracts every function, variable, call and import in a source tree
with a **deterministic** pipeline (tree-sitter grammars, a networkx call graph,
content-fingerprint caching) and uses an LLM for **one thing only**: writing
the prose that describes each extracted symbol. Boundaries, IDs, links, tables
and ordering are all produced by code; the LLM can only fill in (or fail at)
human-readable text. Reruns are stable — unchanged symbols are never
re-generated, and changing one file invalidates only the symbols that live in
it.

Supported languages: **Lua** and **Python** (each backed by its official
tree-sitter grammar; adding a language is a single small backend file).

---

## What it produces

For a source tree, doc_maker writes a `doc/` directory (path configurable):

```
doc/
  index.md                 # entry page: project overview + file list
  <path/to/file>.md        # one page per source file:
                           #   - file summary (LLM prose)
                           #   - variables table (name, init kind, doc)
                           #   - function docs (signature table + developer
                           #     comment if present + prose + source +
                           #     imports/calls context)
  meta/
    symbols.json           # cached analysis (deterministic extraction)
    graph.json             # call/import/containment graph
  .doc_cache               # relpath -> md5 of every file, written after a
                           # clean run; detects changed/removed files on
                           # startup and re-runs just those
```

Plus a `data/` directory of per-record JSON (functions, variables, summaries,
long-function chunks) — this is the LLM-output cache keyed by content
fingerprint.

## Quickstart

1. **Python 3.11+ venv** (3.14 used here):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install tree-sitter tree-sitter-lua tree-sitter-python ruamel.yaml networkx rich
   ```

2. **Secrets** — never put API keys in the YAML config. Create `.env` next to
   the config file:

   ```dotenv
   api_key=sk-...
   base_url=https://your-llm-endpoint/api/v1
   ```

   Config values `api_key: env` / `base_url: env` (also the default when the
   keys are absent) mean "read from `.env`". The lookup order is the config
   file's directory first, then the script directory.

3. **Run**:

   ```powershell
   .\.venv\Scripts\python -X utf8 main.py --config settings.yaml
   ```

CLI flags:

| flag | effect |
|---|---|
| `--config PATH` | settings file (default `settings.yaml`) |
| `--fresh` | ignore the analysis cache and re-extract everything |
| `--no-llm` | skip the LLM phase entirely (extraction + graph + render only) |
| `--purge` | delete all docs/meta/data (output + data dirs) and exit |
| `--regenerate` | delete all docs/meta/data, then run the whole pipeline fresh |
| `--serve` | serve the rendered docs over HTTP instead of generating (needs a previous run) |

## Serving the docs (web)

After a run has produced the markdown docs, `--serve` starts a small stdlib
HTTP server (no extra dependencies) that renders each `*.md` page to themed
HTML in the browser:

```powershell
.\.venv\Scripts\python -X utf8 main.py --config settings.yaml --serve
```

- URLs mirror the docs directory (`/index.md`, `/files/<path>.md`), so all
  internal links and `#fn-...` anchors work unmodified.
- Server settings live in `web/web_settings.yaml`: `host`, `port`,
  `default_theme` (light or dark) and an optional `docs_dir` override.
- Each page has a light/dark toggle button; the choice is remembered per
  browser (localStorage). Themes are plain CSS in
  `web/themes/light/style.css` and `web/themes/dark/style.css`.
- Source code is syntax-highlighted in the browser by
  [highlight.js](https://highlightjs.org/) 11.11.1 — one vendored full
  browser bundle plus its light/dark theme CSS in `web/lib/` (served from
  `/lib/...`; the build does not auto-init, so `web/app.js` calls
  `hljs.highlightAll()` on load). The
  code theme follows the page theme toggle. The server itself stays
  stdlib-only; highlight.js is the single third-party client-side asset.
- Every function's source block is wrapped in a collapsible `<details>` zone
  that is **closed by default**, and its call graph, when present, gets its
  own zone right next to it — so pages stay readable and the code can be
  unrolled on demand.
- Rendering is deterministic (`web/render.py`) — only the markdown subset
  doc_maker itself generates is supported.

## Configuration

Everything lives in one YAML file (see `settings.yaml` for a fully annotated
example). Relative paths resolve against the config file's directory.

| key | meaning |
|---|---|
| `project.source_dir` | root of the source tree to scan |
| `project.output_dir` | where `*.md` pages are written |
| `project.data_dir` | LLM-record cache (`functions/`, `variables/`, `summaries/`, `chunks/`) |
| `project.exclude` | directory names to skip (matched per path component) |
| `project.max_file_bytes` | skip files larger than this |
| `project.copy_meta` | also copy `graph.json` + `symbols.json` into `<output_dir>/meta` |
| `llm.base_url` / `llm.api_key` | endpoint + key; `"env"` (default) reads `.env` |
| `llm.model` | model name |
| `llm.max_retries` / `timeout` | per-request retry/timeout policy (urllib, 300 s default) |
| `llm.temperature` / `max_tokens` | generation parameters |
| `context.*` | how much graph context (imports, call targets, referenced vars) is shown to the LLM per symbol |
| `documentation.*` | toggles + budgets: `skip_existing`, `max_function_lines` (chunk-and-merge threshold), chunking knobs below — **no task caps**: every function, variable and file gets documented |
| `concurrency` | parallel LLM agents working the task queue (default **2**; any positive integer, 20+ is fine) |
| `tui.enabled` / `tui.interval` | live terminal UI while the LLM phase runs (auto-off when stdout is not a TTY) |
| `prompts.*` | system-prompt text files per task kind |

### Long functions: chunk-and-merge

Functions longer than `max_function_lines` (20) are not sent whole. Their body
is split into token-budgeted chunks (`chunk_target_tokens` × `chars_per_token`,
hard-capped at `max_chunk_lines`), each chunk is summarized into a "body note"
(its own cache record), and the final function doc is generated from the
signature plus those notes. This keeps prompts bounded for very long functions
without losing which code was covered.

## Determinism & caching

- **Extraction is pure code.** Function/variable boundaries, IDs
  (`fn:<file>::<name>@<line>`), the call graph and the render order are
  computed from the source text alone.
- **Content-fingerprint cache.** Every LLM record stores the fingerprint of
  its input (function body / variable record / file content). An unchanged
  fingerprint → the record is reused, no API call. A changed one → regenerated.
  `skip_existing: true` makes reruns cheap and resumable.
- **`.doc_cache` (file-level integrity).** After a clean run (no failed
  tasks) the tool writes `<output_dir>/.doc_cache`: every documented file's
  relpath → md5. On startup each hash is compared with the file's current md5;
  a mismatch (or a file that disappeared) marks the cache dirty — the cached
  records of *just those files* are deleted, the analysis cache is ignored,
  and only those files are re-generated. Unchanged files keep their prose.
  A run with failures does **not** update `.doc_cache`, so an interrupted or
  partially failed run can never poison the cache: the next run re-tries the
  missing pieces and reuses everything else.
- **LLM output is validated JSON** (name + prose); invalid responses are
  retried (`retry_invalid_json`) and rejected, they can never corrupt a record.
- **Concurrency changes nothing.** Workers only parallelize *which task runs
  next*; task selection, ordering and fingerprints are independent of it.

The pipeline stages:

```
scan (os.walk, sorted)            -> file list + scan fingerprint
extract (tree-sitter backend)     -> functions / file_vars / calls / imports
build_graph (networkx MultiDiGraph) -> CONTAINS, CALLS, IMPORTS edges
llm_phase (ThreadPool workers)   -> prose records, cached by fingerprint
render (markdown)                -> doc/<file>.md + index.md + meta/
```

## Concurrency & TUI

`concurrency: N` runs N stateless LLM workers over a shared task queue
(`ThreadPoolExecutor`; the HTTP client is a plain urllib call per task, so it
is thread-safe). For big codebases set it to 10, 20, … — the queue size is
unbounded.

While the LLM phase runs, a terminal UI built on [Rich](https://github.com/Textualize/rich)
shows per-agent activity, a progress bar, done/skipped/failed counts, average
time, elapsed time and ETA, plus a log tail. Rich re-lays the whole panel out
on every refresh and measures the terminal itself, so it follows live window
resizes and is never clipped or misaligned at any width. The TUI turns itself
off automatically when stdout is not a TTY (e.g. when run from this kind of
tooling), so log output stays plain in both cases.

## Adding a language

The full standard — contract, record shapes, invariants, the
developer-comment glue rule, registration steps — is in
[`backends/backend_design.md`](backends/backend_design.md). In short:
`backends/__init__.py` maps file extensions to an `extract(source, relpath)`
function returning:

```python
{
  'functions': [{'id', 'name', 'qualified', 'line', 'end_line',
                 'params', 'vararg', 'body'}],
  'file_vars': [{'name', 'line', 'init': empty|table|string|number|function|call|expr}],
  'calls':     [{'callee', 'line', 'method': str|None}],
  'imports':   [{'module', 'line'}],
}
```

(1-based lines, `body` = the source lines of the function.)

A backend also exposes `BUILTIN_NAMES` (names that are not cross-file links)
and the graph asks `backends.module_candidates(module, relpath)` for the file
paths a module import could resolve to. Implement both for the new language,
register its extension in `EXTRACTORS`, install its tree-sitter wheel, done.
`backends/lua.py` and `backends/python.py` are the reference implementations.

## Repository layout

```
main.py            # CLI, config, scan, pipeline orchestration, render
models.py          # small dataclasses / record helpers
util.py            # logging, id sanitizing, truncation, .env reader, fence lang
graph.py           # call/import/containment graph (networkx MultiDiGraph)
documentation.py   # LLM client (urllib), prompt assembly, markdown rendering
tui.py             # terminal UI for the LLM phase (Rich-based)
web/
  server.py        # --serve: stdlib HTTP server + web_settings.yaml loader
  render.py        # deterministic markdown (doc_maker's subset) -> HTML
  app.js           # light/dark theme toggle (persisted per browser)
  web_settings.yaml# host / port / default_theme / docs_dir for the server
  themes/light/style.css, themes/dark/style.css  # the two themes
  lib/
    highlight.min.js   # vendored highlight.js 11.11.1 full UMD build
    github.min.css     # vendored highlight.js light theme
    github-dark.min.css# vendored highlight.js dark theme
    LICENSE            # highlight.js BSD-3-Clause license (required)
backends/
  __init__.py        # extension -> extractor registry + shared helpers
  backend_design.md  # the backend contract (read this before adding a language)
  lua.py             # Lua backend (tree-sitter-lua)
  python.py          # Python backend (tree-sitter-python)
prompts/           # system prompts: function / chunk / variable / summary
settings.yaml      # default config (game codebase)
settings_test.yaml # small local test corpus
settings_self.yaml # doc_maker documenting itself (Python)
```

## Design notes

- **Small on purpose.** No test suite, no framework. The whole system is
  ~2.5k lines of plain Python plus two backend files; the optional web
  server is stdlib-only (no Flask).
- **LLM as a prose oracle, not a parser.** Anything that must be correct
  (names, lines, links, ordering) is computed; the model only explains.
- **Secrets stay out of the repo.** `.env` is git-ignored; the config only
  ever references `env`.
- **Self-hosting check:** `settings_self.yaml` runs doc_maker on its own
  Python sources — a continuous sanity check that the tool documents code.
