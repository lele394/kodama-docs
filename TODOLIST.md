# TODOLIST

Open items from the quality review of kodama-docs. Not yet done. Roughly
ordered by priority; each item says *where* to look.

## High priority — look at these first

- [ ] **Review the prompts** (`prompts/function.txt`, `function_chunk.txt`,
      `variable.txt`, `summary.txt`). `function.txt` opens with "You are
      documenting **Lua** source code from a game installation" — but the
      same prompts are used for every corpus, including the Python
      self-documenting run (`configs/self.yaml`). Decide: make them
      language-neutral, or select the prompt file per `source_extensions`.
- [ ] **Unescaped HTML in the web layer** (injection paths; low severity
      because the server is loopback-only, but they are real):
      - `web/render.py:35,53-57` — any `<...>` tag in markdown text passes
        through unescaped. Only the generated `<a id="...">` anchors should
        pass; LLM prose (or a code comment it echoes) could inject
        `<script>` into served pages. Fix: whitelist anchor tags, escape
        everything else.
      - `web/server.py:161` — the 404 handler reflects the request path
        unescaped into the error page.

## Reproducibility & docs

- [ ] Add `.gitattributes` with `* text=auto eol=lf` — ends the CRLF
      churn warnings on every commit.
- [ ] README L62-63: says the `.env` lookup order is "config file's
      directory first, then the script directory" — the code checks the
      **project root first** (`kodama_docs/config.py:26`). Fix the sentence.
- [ ] Unknown config keys are silently ignored (`kodama_docs/config.py`):
      a typo'd key falls back to the default with no warning. Add a
      warning (or schema check) for unrecognized top-level keys.

## Correctness / robustness

- [ ] Same-name symbol collisions resolve first-come in sort order
      (`kodama_docs/graph.py:101-122`) — deterministic, but can link to the
      wrong function of the same name. Decide on a better disambiguation
      (e.g. prefer same-file/same-module).
- [ ] `web/theme_state.json` is written non-atomically under
      `ThreadingHTTPServer` (`web/server.py:126-130`) — torn write could
      corrupt the theme choice. Write to temp + replace.
- [ ] The determinism baseline check is manual (SHA-256 of the 7 docs,
      kept in a Temp file). There is no automated "did the output change"
      guard. Consider a small `check_baseline.py` or a script in the repo.

## Code smells (refactors — deferred)

- [ ] `backends/lua.py:19` imports helpers from the package `__init__`,
      which imports `lua` at dict-construction time — only works because
      of block ordering. Restructure so the shared helpers live in a
      neutral module.
- [ ] `web/server.py:21-28` try/except import shim creates a second,
      undocumented `log` path (bare `print`). Unify.

## Housekeeping

- [ ] `configs/cloudcfg.yaml` is untracked (scratch config) — decide:
      commit it or add to `.gitignore`.
- [ ] `DESIGN.md` directory tree omits `web/` (~1.5k lines of JS/CSS).
- [ ] **Create a relevant test codebase** — a proper multi-file corpus to
      drive the upcoming polish/bug-fix work. Cover the edge cases the
      current 6-file corpus misses: long functions (chunk-and-merge path),
      same-name functions in different files (collision resolution),
      circular imports, unicode identifiers/comments, `--` comments in
      strings, large files, excluded dirs.

## Done

- [x] **`--no-llm` redesign** (this session): the flag now skips only the
      LLM *model calls* (`kodama_docs/llm.py:generate(no_llm=True)` returns
      per-kind placeholder prose, no network). The whole document still
      renders: descriptions get the explicit "No description generated
      (`--no-llm`)" stub, **Parameters** come from the static analysis
      (`markdown.py:render_file_md`), **References** fall back to the graph
      (call targets + read file vars, `markdown.py:static_references`),
      call graphs were already deterministic. Stubs are cached with a
      `stubbed` flag (`kodama_docs/records.py`); full runs treat them as
      cache misses and regenerate real prose over them — the cache is never
      poisoned. Verified on both test corpora (lua: byte-identical LLM-mode
      output; python: stub run → full run regenerates every task).
- [x] **Render-phase performance** (this session): `render_all` no longer
      pays O(F×E) — `markdown.py:build_call_indexes` makes one O(E) pass
      over the graph and `callers_of`/`callgraph_section` become
      O(in-degree) lookups; the symbol index is built once per run.
      Benchmark (20k nodes / 120k edges, 2k functions documented): old
      per-function edge scan 56.5s → new 0.15s (~380× faster), identical
      results.
- [x] **Environment rebuild** (this session): removed `.venv` (py3.15) and
      `.venv314` (py3.14), created a fresh `.venv` from Python 3.14.8 with
      a pinned `requirements.txt`, verified pipeline + imports.
