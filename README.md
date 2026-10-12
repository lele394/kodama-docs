<p align="center">
  <img src="icon/icon.png" width="112" alt="kodama-docs icon" />
</p>

<h1 align="center">kodama-docs</h1>

<p align="center">
  <strong>Deterministic documentation generator for codebases.</strong><br />
</p>

kodama-docs extracts every function, variable, call and import in a source tree
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

## Developer notes 

Hi, I'm a PhD student working in sustainable computing. In the last few years,
I've seen AI get thrown at tasks for no real reasons other than for the sake
of it. Lots of code is being generated everyday without any care in the world
for who will actually read it, if anyone actually does. I am myself a victim 
of such crimes, and I hate spending time documenting. This project aims to
provide a tool that uses AI in a smart way: instead of throwing compute at 
the problem, deterministic parts of the workflow is done with good old logic.
AI is here to provide overviews and descriptions, to augment the documentation,
not be its source of truth. I hope this project can help some of you stuck in 
the bowels of strange and unfamiliar code. Cheers!

---

## Planned future 

### Features

- [ ] Manual documentation
- [ ] Graph mode optimizations (high node counts)

### Planned language support 

- [ ] C support
- [ ] C++ support
- [ ] Fortran support
- [ ] Rust support

### Long-term planned feature

- [ ] Smart Git integration (use diffs to decide what to reprocess)

### Planned review

I will experiment a lot with how the system handles context for the summaries.
This is bound to potentiall change a lot. Same goes for pronts, where sometimes,
I expect the need for language-specific prompts. This will also be addressed.

Due to the limited amount of time that me, and my trusty Qwen3.8 27b with its 
RTX3090 have, dev might be slow. Helping hands are always welcome!

---

## What it produces

For a source tree, kodama-docs writes a `doc/` directory (path configurable):

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

1. **Python 3.11+ venv** (Linux/macOS; 3.14 used here):

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   (or `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt`)

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

   ```bash
   .venv/bin/python -X utf8 main.py --config settings.yaml
   ```

CLI flags:

| flag | effect |
|---|---|
| `--config PATH` | settings file (default `settings.yaml`) |
| `--fresh` | ignore the analysis cache and re-extract everything |
| `--no-llm` | skip the LLM **model calls** only: placeholder prose is cached (flagged), all deterministic sections — parameters, references, call graph — are still generated |
| `--purge` | delete all docs/meta/data (output + data dirs) and exit |
| `--regenerate` | delete all docs/meta/data, then run the whole pipeline fresh |
| `--serve` | serve the rendered docs over HTTP instead of generating (needs a previous run) |

## Serving the docs (web)

After a run has produced the markdown docs, `--serve` starts a small stdlib
HTTP server (no extra dependencies) that renders each `*.md` page to themed
HTML in the browser:

```bash
.venv/bin/python -X utf8 main.py --config settings.yaml --serve
```

- URLs mirror the docs directory (`/index.md`, `/files/<path>.md`), so all
  internal links and `#fn-...` anchors work unmodified.
- Server settings live in `web/web_settings.yaml`: `host`, `port`,
  `default_theme` (light or dark) and an optional `docs_dir` override.
- Each page has a light/dark toggle button; the choice is remembered per
  browser (localStorage). Themes are plain CSS in
  `web/themes/light/style.css` and `web/themes/dark/style.css`.
- The docs and `/graph` pages share one fixed-height top bar (56px) so the two
  views line up. The project icon (`icon.png` / `icon.ico` in the repo-root
  `icon/` folder, served read-only at `/icon/...`) is set as the browser
  favicon and shown next to the `kodama-docs` brand on both pages.
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
- **Sidebar — file tree + fuzzy search** (docs pages only; `web/sidebar.js`).
  A permanent left sidebar (always visible — no toggle button) spans the full
  page height: the search box is pinned at the top, the file tree fills the
  remaining space and scrolls internally (no page-level scrollbars), and the
  sidebar can be **resized** by dragging its right edge (5px `col-resize`
  handle, clamped 200–640px, remembered per browser in
  `kodama.sidebar.width`). The handle lights up blue while hovered or
  dragged, the same cue as the `/graph` panel divider. It mirrors the doc
  directory hierarchy with
  per-directory and per-file collapse, each file's function and variable
  symbols, and an `index` row at the top — so multi-level folders
  (`physics/body.lua`, `sim/render.py`, …) render as nested, expandable
  branches.

  **Search.** The box fuzzy-matches files, functions and variables (same
  subsequence scorer as the `/graph` bar, `web/fuzzy.js`) and replaces the
  tree with the ranked hits, **grouped by file** — each file is one header
  row (clicking it opens that file's page) followed by its matching
  symbols. `Enter` opens the first hit, `Esc` clears, `/` focuses the box.
  Function rows link to their `#fn-…` anchor; variable rows link to the
  page's `#variables` section (markdown only generates one anchor per
  file's variables). The active query is kept in the URL as `?q=…`
  (`history.replaceState`), so a result can be shared and survives a
  reload; clearing the search removes it.

  **Query grammar** — whitespace-separated tokens are ANDed together:

  | token | meaning |
  | --- | --- |
  | `word` | fuzzy-matches any candidate's name (or a function's qualified name) |
  | `@fn` / `@var` / `@file` | pure **type filter** — only that kind of symbol matches |
  | `@fn:word` `@var:word` | that kind, whose **name** fuzzy-matches `word` |
  | `@file:word` | **path scope** — files whose path matches `word` match, and non-file candidates are kept only if their file's path matches `word` |
  | `@unknown` | treated as the bare word `unknown` |

  Examples: `@file:physics @fn step` → the `step` function, but only under
  files whose path matches `physics`; `@var buf` → variables named ~`buf`;
  `connect @file:net` → `connect`-like symbols scoped to `…/net/…`. (A bare
  `@file` matches files only and does *not* scope other kinds.)

  **Clicking a file row** is context-aware: if that file is the page you're
  already on, the click just toggles its expansion (no reload, so you stay
  exactly where you were); otherwise it navigates to the file *and* expands
  it, so its symbols are visible on arrival.

  Sidebar expanded state and width are stored per browser (localStorage:
  `kodama.sidebar.expand`, `kodama.sidebar.width`) — deliberately unlike the
  theme, which the server persists for all browsers. Data comes from a slim
  `/api/symbols`
  endpoint (a trimmed `meta/symbols.json` with function bodies stripped).
- **`/graph` — interactive dependency graph.** Built from `meta/graph.json`
  by `web/graph.js` (vanilla JS + canvas, no libraries), with two levels:
  **files** (one node per file; imports kept, calls re-aggregated
  file→file) and **functions** (functions and variables as nodes with
  CONTAINS / CALLS / READS edges; external and built-in symbols can be
  toggled on). Clicking a node opens its documentation in the left panel —
  in-panel links navigate within the panel, with a back button. Drag to
  move nodes, scroll to zoom, drag the background to pan. The layout is a
  force simulation with a fixed seed, so the same graph always settles into
  the same arrangement.
- Rendering is deterministic (`web/render.py`) — only the markdown subset
  kodama-docs itself generates is supported.

## Testing on the sample codebases

`test_codebases/` holds two small, self-contained **N-body simulation**
samples — one per supported language — built to exercise every feature:
file/variable/function extraction, developer-comment gluing (including a
deliberate negative case), long functions for chunk-and-merge, method and
class style OOP, and external-module imports. The sources are organised in
**nested folders** (e.g. `codebase/physics/`, `codebase/sim/`) and their
`require`/`import` statements use dotted module paths (`physics.nbody`,
`physics.body`, `sim.render`), so the samples also exercise multi-level
directory handling and nested-import resolution end to end (the graph's
IMPORTS edges resolve to the real file nodes, and the sidebar renders the
folders as a nested tree). Generated docs land in
`test_codebases/<lang>/docs/` (mirroring the nesting under `docs/files/`),
the LLM cache in `test_codebases/<lang>/data/`.

To run the tool on a sample (from the repo root):

```bash
source .venv/bin/activate
python main.py --config test_codebases/lua/settings.yaml
python main.py --config test_codebases/python/settings.yaml

# then browse the results in the browser:
python main.py --config test_codebases/lua/settings.yaml --serve
```

Notes:

- The LLM phase needs an `.env` (it already exists in both sample dirs and at
  the repo root — all git-ignored); `base_url: env` / `api_key: env` in the
  sample configs pick it up, config directory first, then repo root.
- Runs are fingerprint-cached, so re-running is cheap — unchanged symbols are
  never re-generated. `--fresh` re-extracts from scratch, `--no-llm` skips
  the LLM model calls (placeholder prose is cached with a `stubbed` flag,
  which a full run treats as a cache miss and overwrites with real prose),
  `--regenerate` wipes `docs/` + `data/` and rebuilds everything.
- The samples are small on purpose so a full run (a few dozen LLM tasks at
  `concurrency: 4`) finishes quickly even on a slow local endpoint.

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
build_graph (networkx MultiDiGraph) -> CONTAINS, CALLS, IMPORTS, READS edges
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
main.py            # CLI + pipeline orchestration (thin; the phases live in kodama_docs/)
kodama_docs/          # all pipeline modules
  config.py        # settings + .env loading
  scan.py          # file scanning, analysis cache, per-file analysis
  graph.py         # call/import/containment graph (networkx MultiDiGraph)
  context.py       # LLM prompt context assembly
  records.py       # read/write LLM records (data/functions|variables|summaries)
  outputs.py       # doc cache, purge
  llm.py           # LLM client (urllib, OpenAI-compatible)
  llm_phase.py     # LLM task queue + TUI wiring
  markdown.py      # deterministic markdown rendering
  models.py        # output schemas + deterministic JSON validator
  tui.py           # terminal UI for the LLM phase (Rich-based)
  util.py          # logging, id sanitizing, truncation, .env reader, fence lang
web/
  server.py        # --serve: stdlib HTTP server + web_settings.yaml loader
  render.py        # deterministic markdown (kodama-docs's subset) -> HTML
  app.js           # light/dark theme toggle (persisted per browser)
  sidebar.js       # docs-page sidebar: file tree + fuzzy symbol search
  fuzzy.js         # shared fuzzy subsequence scorer (sidebar + /graph bar)
  graph.js         # /graph page entry point (thin; the modules live in web/graph/)
  graph/           # ES modules: state, layout, draw, interact, panel, controls, ...
  templates/       # page.html, graph.html (the page shells, no server-side HTML)
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
test_codebases/    # small lua + python N-body samples for end-to-end testing
configs/
  test.yaml        # small local test corpus
  self.yaml        # kodama-docs documenting itself (Python)
```

## Design notes

- **Small on purpose.** No test suite, no framework. The whole system is
  ~2.5k lines of plain Python plus two backend files; the optional web
  server is stdlib-only (no Flask).
- **LLM as a prose oracle, not a parser.** Anything that must be correct
  (names, lines, links, ordering) is computed; the model only explains.
- **Secrets stay out of the repo.** `.env` is git-ignored; the config only
  ever references `env`.
- **Self-hosting check:** `configs/self.yaml` runs kodama-docs on its own
  Python sources — a continuous sanity check that the tool documents code.

## License

Licensed under the **MIT License** — see [LICENSE](LICENSE). On top of the
standard MIT grant, the license carries one extra condition: this project's
source code and documentation may **not** be used as training, fine-tuning,
or evaluation data for AI/ML models (including large language models).
