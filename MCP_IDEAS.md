# MCP server — design

A single MCP (Model Context Protocol) server for kodama-docs, investigated
2026-10. This is a design sketch, not an implementation. Status: proposed,
**one server, flag-gated**.

The short version:

- **One server, flag-gated.** `main.py --mcp` is a read-only MCP over an
  already-generated docs set: the agent searches symbols fuzzily, pulls one
  record, walks the call graph, and follows leads instead of reading whole
  files. It is the **default** — read-only and safe to share.
- **`--edit`** adds a prose-editing tool (the agent fixes an LLM-generated
  description in place, without a full rebuild). **`--build`** adds
  agent-driven documentation builds. Both write to the install, so both are
  **local stdio only**.
- Read/write separation is a **capability gate** (a CLI flag), not two
  servers: MCP tools are registered at startup, so the flag decides which
  tools exist. A hard transport guard refuses to run the write tools over
  HTTP, so the read-only form is the only one you can expose.
- All three are small because the hard parts (deterministic extraction,
  graph, cached prose, fuzzy scorer) already exist. The MCP layer is just an
  API surface over artifacts already on disk.

**Why one server instead of two** (the earlier draft had "query" + "build"):
the CLI is already flag-style (`--serve`, `--list-backends`, `--install`) so
`--mcp` fits; read and write read the same `symbols.json` + `graph.json` so
one process loads them once; one host registration instead of two, with the
safe default being the read-only form (opt-*in* to write). The only thing two
servers bought was a *simultaneously* shared read + local write instance —
and that is just two processes of the same binary with different flags.

---

## What we already have (the "db")

| Artifact | Content |
|---|---|
| `data/symbols.json` | Per file: functions (`id`, `name`, `qualified`, `line`, `end_line`, `params`, `body`, `developer_comment`), `file_vars`, `calls`, `imports` |
| `data/graph.json` | NetworkX node-link: nodes `file` / `function` / `variable` with stable ids (`fn:<file>::<name>@<line>`); edges `CALLS`, `CONTAINS`, `READS`, `IMPORTS` |
| `data/{functions,variables,summaries,chunks}/*.json` | One JSON per record: deterministic symbol fields + LLM `prose` (keyed by content fingerprint) |
| `docs/` | Rendered markdown: `index.md` + `files/<relpath>.md`; anchors `#fn-<name>-<line>`, `#variables` |
| `web/fuzzy.js` + `web/sidebar.js` | Deterministic subsequence fuzzy scorer **plus a full query grammar** (see below) — currently JS only |

**The query grammar already exists and is worth reusing.** The web sidebar
search (`web/sidebar.js`) parses whitespace-separated tokens combined with
AND:

```
word            fuzzy-match a symbol/file's own name
@fn  @var       type filter: functions / variables only
@file           type filter: files only
@fn:con         function names fuzzy-matching "con"
@var:i          variable names fuzzy-matching "i"
@file:src       path scope: keep candidates in files under ~src
```

`parseQuery` + `scoreCandidate` + `fuzzyScore` are ~100 lines of pure JS,
deterministic, no DOM. Examples: `@file:physics @fn step` → the `step`
function, but only under `physics/`; `@var buf` → variables named ~`buf`.

**Design consequence:** the `search` tool should accept *exactly this
grammar* — the same query a human types in the web UI returns the same ranking
via MCP. One query language across both surfaces, and the port is bounded
(~100 LOC of Python).

Scale sanity: the render benchmark already ran 20k nodes / 120k edges, so
loading `symbols.json` + `graph.json` into memory for the query server is
cheap (hundreds of ms, tens of MB).

---

## Server topology: one binary, three flags

| Command | Surface | Posture |
|---|---|---|
| `main.py --mcp` | read: `index · search · get · neighbors · file` | **default**, read-only — safe to expose over HTTP later |
| `main.py --mcp --edit` | + `edit(symbol, text)` | writes disk — **local stdio only** |
| `main.py --mcp --edit --build` | + `build · status` | writes + spends tokens — **local stdio only** |

- **Flag = capability gate.** MCP tools are registered at startup, so the flag
  decides the tool list. No flag → the write tools are not in the list at all,
  so a host that shares the server over HTTP gets a genuinely read-only
  surface.
- **Hard transport guard.** If `--edit`/`--build` is set and the transport is
  HTTP/SSE, the server exits with a clear error (or strips the write tools +
  warns). You cannot accidentally expose `edit`/`build` even with a
  misconfigured host — more robust than the two-server split, where a human
  could mis-register the write server.
- **Naming note:** `--edit` means "the LLM may modify prose". If you'd rather
  one switch cover both write tools, `--write` is the more accurate name (since
  `build` writes too). Current lean: keep `--edit` (prose) and `--build`
  (pipeline) as separate flags — `edit` spends no tokens, `build` does.
- **Where it lives:** `kodama_docs/mcp_server.py` (or an `mcp_server/`
  package); config = `--docs-root` / env var. Reuses `config.load_config`,
  `records.list_records`, `graph` helpers. The build path reuses the
  subprocess machinery described below.

---

## Read surface (`main.py --mcp`)

**Goal.** An LLM agent working in/against a codebase stops reading whole
source files and instead: `search("apply force")` → gets a ranked list with a
one-line description each → `get()` the promising one (prose + signature +
source + where it's called from) → `neighbors()` to walk callers/callees →
repeat. The graph *is* the lead-following mechanism.

**Shape.** One server instance = one generated docs set (point it at the
`data/` + `docs/` roots). Want to query three codebases? Run three instances —
that's the normal MCP pattern (one Serena instance per project, etc.).

### Tools

| Tool | Returns | Notes |
|---|---|---|
| `index()` | project overview: file list with summaries, counts, docs-set identity (root, fingerprint, mtime, staleness) | entry point; staleness via the existing `outputs.check_doc_cache` |
| `search(query, limit=10)` | ranked symbol list: id, kind, qualified name, `file:line`, score, one-liner (record prose if present, else dev comment) | `query` is the **existing sidebar grammar** (words + `@fn`/`@var`/`@file` filters + `@file:word` scope, AND-combined); port `fuzzyScore` + `parseQuery` + `scoreCandidate` to Python — same scores, same ranking as the web UI |
| `get(symbol, format="record"\|"md")` | full record: prose description, params, source body, dev comment, file:line, doc page anchor — or (with `format="md"`) the rendered markdown section | `symbol` = stable id or fuzzy name; `format="md"` is the old `open_doc`, folded in |
| `neighbors(symbol, direction=out\|in\|both, limit)` | typed edge list (`CALLS`/`READS`/`IMPORTS`/`CONTAINS`), same shape as `search` | the "follow the lead" tool: who calls this, what it calls, which vars it reads, containing file. Adjacency index built once at startup; **no `types` filter** — always return typed edges |
| `file(symbol)` | file record: summary prose, function/var list with one-liners, imports | the most-cuttable read tool if you want to go to 4 |

### Removed from the earlier draft (and why)

- **`query_guide()`** — MCP hosts already surface each tool's **docstring** to
  the agent; the grammar lives in `search`'s docstring. A meta-tool is
  redundant surface.
- **`open_doc()`** — merged into `get(format="md")`.
- **`path(a, b)`** — was marked *(stretch)*; defer until agents actually ask
  "why do these two relate."

**Design decisions** (read side)

- **Read-only, stateless** → the shareable server. Zero new dependencies
  beyond the MCP SDK (+ pydantic); the fuzzy scorer is a port of the JS one
  (keep the same scores → same results as the web UI).
- **LLM-friendly output:** compact JSON with stable ids so calls chain
  (`search` → `get` → `neighbors` → `get`…); one-liners by default, full body
  only on explicit `get`. Keep default payloads under ~1–2k tokens so an
  agent can afford 10–20 lookups in a context window.
- **Staleness reporting:** at startup record `symbols.json` fingerprint +
  mtime, surface it in `index()` ("docs generated from source state X at T;
  source has N files newer"). The logic already exists
  (`outputs.check_doc_cache`) and is reusable.

**Effort.** ~200–400 LOC: JSON loader + adjacency index, fuzzy port, 5 tools,
SDK wiring. Low risk.

---

## Write surface, part 1: `--edit` (prose editing)

**Goal.** When a generated description is wrong or weak, the agent fixes it
**in place** — no full `--fresh` rebuild, no hand-editing a generated file
that the next run clobbers.

**The line the tool enforces (this is the whole point).** The deterministic
record — `name`, `params`, `line`, `end_line`, `qualified`, `body`, `calls`,
`imports`, and the graph — is regenerated from source and is the **source of
truth**; the LLM never writes it. `edit` draws a **read vs write** line, not
an "expose or not" one:

- `get` **returns** the deterministic fields (read) — fine and useful.
- `edit(symbol, text)` **writes only prose** — the function description, a
  variable description, or the file summary (which one is inferred from the
  record kind). It physically cannot touch `params`, `line`, `body`, `calls`,
  or the graph.

### Tool

| Tool | Behavior |
|---|---|
| `edit(symbol, text)` | Writes the agent-authored prose for one symbol (function/variable/file), validates it through the **same schema** the LLM output gets, persists it (below), and returns the updated record with a provenance flag. `symbol` = stable id or fuzzy name. |

### Persistence: the override layer (the real design decision)

The prose cache is keyed by **content fingerprint** and is **overwritten** on
a changed-file / `--fresh` build — so a naive edit is lost. The fix is a thin
override layer that render prefers over the fingerprint cache:

```
data/overrides/<symbol_id>__<fingerprint>.json
```

- **Keyed by (symbol id, fingerprint).** An edit made against source state `X`
  on a symbol whose code is now `Y` is simply *not there* — it auto-drops
  instead of lying about new code. (The alternative — keying by id only —
  would let a stale edit silently survive a code change; don't.)
- **Render prefers the override** over the fingerprint cache for that symbol.
  The deterministic record stays pristine; the edit is a thin annotation on
  top — exactly "AI augments, doesn't own the source of truth".
- No schema change to the record; it is an additive file. Whether
  `--purge`/`--regenerate` clears overrides is a policy choice to document
  (see open questions).

### Provenance

`get` returns a `prose: "llm" | "edited"` field (plus the fingerprint it was
written against) so the agent can weigh the text.

**Posture.** `edit` is a **write** (disk) even though it spends no tokens →
**local stdio only**, behind the transport guard.

**Effort.** ~100–200 LOC: override read/write, the one tool, validation reuse,
provenance flag. Low risk, high value.

---

## Write surface, part 2: `--build` (agent-driven documentation)

**Goal.** The agent *builds* docs for a codebase: "document this repo",
"re-run with --no-llm first to check the extraction", "regenerate after the
refactor". This makes kodama-docs a tool agents can operate, not just read.

**Shape.** The server is the kodama-docs install (it knows where `main.py`,
configs, and `.env` live). The agent passes a config file (or dict) and
options.

### Tools

| Tool | Behavior |
|---|---|
| `build(config, target=None, fresh=False, no_llm=False, regenerate=False)` | Starts a build **as a separate OS process** (`python main.py --config … [flags]`), returns `{job_id, status, log_file}` immediately. `target` overrides `source_dir` (output/data dirs follow) so the agent can document *any* tree, not just configured ones |
| `status(job_id, tail=40)` | `running / done / failed` + progress parsed from the log (files scanned, records done/total — the pipeline already logs both) + the last `tail` log lines; when **done**, also the result: `index.md` head, file count, failed-record count, docs path (so the agent can verify and then re-query) |

### Removed from the earlier draft (and why)

- **`log()`** — merged into `status(tail=…)` (which already returned the log
  tail).
- **`list_configs()`** — the host can read the filesystem; also leaks the
  install layout.
- **`purge()`** — `build(regenerate=True)` already does "delete + rebuild"; a
  pure delete is a human on-disk action.

**Design decisions** (build side)

- **Subprocess + status pair, not one long blocking call.** Some hosts can
  wait (Claude Code auto-backgrounds calls >2 min), others can't (Claude
  Desktop ~4 min) — so `build` returns a job id immediately and the agent
  polls `status` (the GitHub MCP trigger-then-poll shape). Spawning `main.py`
  as a child process also gives: crash isolation (a pipeline bug can't take
  down the MCP server), exact CLI flag parity (`--fresh --no-llm
  --regenerate`), and trivial log capture (redirect to a file, tail it). Job
  state = pid + log path + a status file the exit code updates. (An MCP
  *Tasks extension* version — durable `taskId` + progress — is a possible
  later upgrade.)
- **Concurrency guard:** one build per resolved `data_dir` at a time — the
  records cache is not built for two writers. The job manager refuses a second
  build whose config resolves to the same `data_dir` (cheap: hash the resolved
  config), or uses a lockfile.
- **Spend/permission model:** this server triggers LLM calls with the
  configured API key and writes to disk → **local stdio only** (transport
  guard), or 127.0.0.1 + token if it must be remote. Document the key exposure
  explicitly.
- **Where it lives:** shares the `mcp_server` package with the read/edit
  surfaces; the job manager is ~80 LOC.

**Effort.** ~150–250 LOC: job manager + 2 tools. Main risk is the concurrency
guard and log parsing, both small.

---

## The MCP layer itself (SDK, hosts, conventions)

Findings from checking the protocol/SDK state (late 2026):

- **SDK.** `pip install mcp` now resolves to **v2** (FastMCP was renamed
  `MCPServer`, `from mcp.server import MCPServer`; the v1 `fastmcp` import
  path is gone from v2 but still published as `mcp<2`). For our simple server
  the two APIs are near-identical: decorator tools, **function name = tool
  name, docstring = description, type hints → JSON schema**, return `str` for
  text content, `mcp.run()` = stdio server. Sync `def` tools run on a worker
  thread, so blocking JSON loads/queries are fine — no asyncio needed.
  Minimal shape (v2):

  ```python
  from mcp.server import MCPServer
  mcp = MCPServer("kodama-docs")

  @mcp.tool()
  def search(query: str, limit: int = 10) -> str:
      """Search the codebase docs. Grammar: word | @fn @var @file filters,
      @fn:name, @file:path-scope; AND-combined (same as the web sidebar)."""
      return "…ranked results…"

  if __name__ == "__main__":
      mcp.run()   # stdio, default
  ```

  The flag gate happens *before* this: the server only *registers* the
  `edit`/`build` tool functions when the corresponding flag was passed, so an
  un-flagged process has no write tools to expose at all.

- **Dependencies.** The SDK hard-depends on **pydantic** (not in our venv
  today) — so "zero new deps" means *zero beyond `mcp` + pydantic*. Keep the
  MCP server an optional extra (`requirements-mcp.txt`, or `pip install mcp`
  in the venv when wanted) so the core pipeline stays dependency-free.
- **Errors.** Raise `ToolError` for fixable failures (message goes back to the
  model, `is_error=true`); keep protocol errors for protocol problems. Our
  tools: "no docs found for root X" / "unknown symbol id" are `ToolError`
  cases with the candidate ids listed.
- **Tool naming (2026-07-28 spec):** 1–128 chars, `[A-Za-z0-9_.-]`, unique
  per server. Our names comply.
- **Host timeouts (this shapes `--build`).** Claude Code: tool timeout
  default ~28 h, calls >2 min auto-backgrounded → long blocking tools *work*
  there. Claude Desktop: ~4 min tool execution cap (unofficial) + 60 s
  initialize. So the portable pattern is still **start + status pair** (what we
  propose); there is also an official **Tasks extension** (durable `taskId` +
  polling) worth adopting later if hosts support it.
- **Transport.** stdio is the right default (host launches us as a child; no
  port, no auth — and it's how the host already isolates our spend).
  Streamable-HTTP is available out of the box in the SDK if the read surface
  ever needs to be shared; SSE is legacy, don't build on it. **The transport
  guard** (from the topology section) is what keeps `--edit`/`--build` out of
  any HTTP/SSE instance.
- **Testing ergonomics.** `pip install "mcp[cli]"` gives `mcp dev server.py`
  (interactive inspector over stdio); v2 also ships an in-memory client for
  unit-testing tools without spawning a process.

**Precedents that validate the design** (and lessons taken):

| Server | Shape | Lesson used here |
|---|---|---|
| **Serena** (symbol IDE for agents, LSP-backed) | `find_symbol` fuzzy entry + cheap `get_symbols_overview` before drilling | fuzzy search as primary entry; cheap `index()` overview tool |
| **Sourcegraph MCP** | `search` over a pre-built index + a meta "how to search" tool | ship the query grammar in the `search` docstring (we drop the separate meta-tool — hosts already surface docstrings) |
| **Context7** | exactly 2 tools: `resolve-library-id` (fuzzy) → `query-docs` (fetch) | keep the surface tiny; two-stage *resolve-then-fetch* is the cleanest fuzzy UX → our `search` → `get` |
| **ripgrep-style servers** (mcp-ripgrep, ripwire…) | exact lexical search; ripwire serves *signatures* not bodies | one-liners by default, full body only on explicit `get` (token cutting) |
| **GitHub MCP server** | `actions_run_trigger` → `list_workflow_runs` → `get_workflow_run_status` | trigger-then-poll is the proven shape for "run a pipeline" tools → `--build` |

---

## How they compose

The end state is one server an agent runs unaided, escalating only when it
needs to:

```
--mcp:      index → search → get / neighbors → …        (navigate)
  → "this description is weak / wrong"
      --edit:   edit(symbol, text)                       (fix in place, no rebuild)
  → "no docs for this module / stale"
      --build:  build(target=that_tree) → status() until done
                → back to --mcp on the fresh docs
```

That's the product: *the agent navigates the docs, fixes the prose it doesn't
like, and builds the docs it's missing — without reading files or re-running
the LLM phase for a one-line fix.*

## Suggested order & open questions

Order (each step is a self-contained, shippable server):

1. **`main.py --mcp`** (read) — 5 tools, no job mgmt, no spend, shareable.
   Validates the data model for MCP consumption. This is the useful 80%.
2. **`--edit`** — the prose tool + override layer + provenance. Cheap,
   on-brand, closes the "bad description" gap.
3. **`--build`** — the pipeline tools + job manager. The complex, spendy
   piece; lands last behind its own flag.

Open questions:

- **Naming:** `--edit` (prose only) + `--build` (pipeline) vs. one `--write`
  covering both. Current lean: separate flags (clearer capability, and `edit`
  spends no tokens while `build` does).
- **Override lifecycle:** does `--purge`/`--regenerate` clear
  `data/overrides/` (fresh start) or preserve edits (annotation survives)?
  Leaning: preserve on `--fresh`, clear on `--regenerate` — document whichever
  we pick.
- **Fuzzy:** pure-Python port (zero deps, same scores as the web UI) vs.
  `rapidfuzz`. Leaning: the port — ~100 lines, preserves determinism, and
  gives one query language for both surfaces.
- **Body search:** the grammar matches names/paths/prose; there is no "search
  inside function bodies" token. Stay at parity with the web sidebar for v1;
  add a `@in:word` body token later if agents want it.
- **Multi-corpus:** one server per docs set (per `--docs-root`) vs. a `corpus`
  param. Per-instance is the MCP norm; the param complicates the tool schema
  and the staleness reporting.
