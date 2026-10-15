# Performance

The pipeline has three phases — **scan/extract** (CPU, fast), **LLM phase** (network-bound, the bottleneck), and **render** (CPU, fast). Almost all tuning is about the LLM phase and the caches that avoid repeating it.

## Make reruns fast (caches)

Three layers mean an unchanged project re-runs in seconds, not minutes:

1. **`.doc_cache`** (`<output_dir>/.doc_cache`) records each scanned file's md5. On the next run, files that changed (md5 differs → "dirty") or were removed since the last cache ("stale") have their cached LLM records deleted and are re-analyzed and re-run; files unchanged are not touched by this layer. It is **only written when a run has zero failed LLM tasks**, so a failed run never marks itself "current".
2. **Record fingerprints** (`data/{functions,variables,summaries,chunks}/*.json`) — each generated record stores a `fingerprint` folding in the symbol's source, its callers/callees, the shaping settings, and the model. A mismatch is a miss; a match is a **skip** (no network call). This is why the phase log reads `skipped=N`.
3. **`symbols.json`** — the per-file extraction cache, keyed by a scan fingerprint and stamped with the backends' `name@version`. Editing source or upgrading a backend invalidates it; `--fresh` bypasses it entirely.

Practical levers:

- Leave `documentation.skip_existing` (default `true`) on — it's what makes the record cache apply.
- Keep `copy_meta` on if you also want the web graph; it only affects render.
- To force a clean rebuild when something looks wrong, `--regenerate` (delete `docs/`/`meta/`/`data/` **and run**) or `--purge` (delete and **exit**).

## Speed up the LLM phase

| Knob | Default | Effect |
| --- | --- | --- |
| `concurrency` | `2` | number of parallel agents. Raise it for big projects (the self-doc config uses `4`); each in-flight task is a network call. |
| `llm.max_tokens` | `900` | reply budget. Bigger → more complete prose but slower and more truncation risk. |
| `llm.timeout` | `300` | per-attempt socket timeout. Lower to fail fast against a hung local server. |
| `llm.max_retries` | `5` | total transport attempts per call. Each adds latency only on failure. |
| `documentation.max_function_lines` | `20` (settings) / off (code) | functions longer than this are split and summarized **chunk-and-merge** (more, smaller LLM calls). Raising it reduces call count but larger requests; lowering it does the opposite. |
| `documentation.chunk_target_tokens` | `20000` | target size per chunk call (≈ `tokens × chars_per_token` chars). |
| `documentation.chars_per_token` | `4` | rough token estimate used in the chunk budgets. |
| `documentation.include_anonymous_functions` | `false` | keep `anon` functions out of the LLM phase to save tokens (they still render). |

**Trim the input**, not just the model:

- `project.exclude` — drop directories that shouldn't be documented (`vendor`, `generated`, `doc`, `test_out`, …).
- `project.max_file_bytes` (default 25 MiB) — oversized files are skipped and reported, not parsed.
- A small corpus is the cheapest speedup of all: document a subtree while developing.

## Monitor a long run

- The **TUI** (`tui.enabled`, default on for a TTY) shows one row per active agent — state, file, symbol, stage, duration — plus per-kind totals and a rolling log tail. Disable with `tui.enabled: false` or run non-interactively.
- The phase ends with a one-line summary: `llm phase: done=… skipped=… failed=… in Ns with M agents`. `skipped` is your cache hit-rate; `failed` tells you what a rerun will retry.
- `--no-llm` is the fastest way to see the *structure* (pages, links, graph) of a large project without any token cost — then do the real run.

## What is *not* a performance problem

- **Orange references** and **`(inferred)`** labels are resolution decisions, not slowness.
- **`analysis: … binary (no symbols extracted)`** is expected for binary files.
- A run that **stops at exit code 1** is a *correctness* outcome (some LLM tasks failed), not a hang — see [LLM Problems](01%20-%20LLM%20Problems.md).

Related: [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md), [Chunk and Merge](../02%20-%20How%20It%20Works/06%20-%20Chunk%20and%20Merge.md), [Config Reference](../04%20-%20Reference/01%20-%20Config%20Reference.md).
