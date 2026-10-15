# Caching

Re-running is cheap. Three independent layers make sure you only pay (in LLM calls and CPU) for what actually changed, and the layers stack.

## The three layers

### 1. File-level cache — `<output_dir>/.doc_cache`

A small JSON file (`kodama_docs/doc_cache@1`) mapping every documented file's relpath to its content md5. On the next run, `check_doc_cache()` compares:

- **changed** (md5 differs) and **stale** (in the cache but the file no longer exists) → their LLM records are deleted and the files are re-analyzed from scratch;
- **unchanged** files → their records are reused as-is.

This is the coarse layer: it decides which files still need analysis and which records stay valid. The cache map is only rewritten when the run completes with **no failed LLM tasks** — a run with failures leaves the map untouched, so the next run retries exactly those files while reusing everything else.

### 2. Per-task records — `<data_dir>/{functions,variables,summaries,chunks}/`

One JSON file per prose task, named `{kind}_{md5(relpath)[:10]}_{name}_{line}.json`. Every record stores a **fingerprint** (schema `kodama_docs/record@1`) computed from *everything* that could change the prose:

- the symbol's name, line, body (or initializer), parameters;
- its graph neighbors (callers and callees for functions);
- the model, base URL, prompt file *content*, and the relevant `context.*` / `documentation.*` settings.

A record is used only when its stored fingerprint matches the freshly computed one. Change the function, change who calls it, change the model or the prompt — the fingerprint differs, the record is a miss, and the task is regenerated. This is what makes "edit one function, re-run, only that function's page changes" work.

### 3. Analysis cache — `<data_dir>/symbols.json`

The extraction itself (tree-sitter parse → records → graph input) is cached per file, stamped with each backend's `name@version` so a backend upgrade invalidates it. `--fresh` bypasses this layer and re-extracts everything (it still honors the record and doc caches).

## How the layers interact

| You … | File cache | Records | symbols.json |
| --- | --- | --- | --- |
| re-run with nothing changed | hit — no re-analysis | all reuse (0 LLM calls) | hit |
| edit one function | changed file → its records deleted → **re-analyzed** | that file's records miss → regenerated | that file re-extracted |
| change model / prompt / `context.*` | unchanged → no re-analysis | **all miss** (settings are in the fingerprint) → regenerated | hit (settings don't stamp it) |
| replace the backend | unchanged | unchanged (fingerprint does not include the backend) | **miss** (backend id changed) → re-extract; prose may then differ with the new records |
| `--fresh` | unchanged | unchanged | bypassed → full re-extract |
| `skip_existing: false` | unchanged | **never loaded** → every prose task re-runs | unchanged |
| `--regenerate` | deleted | deleted | deleted — output *and* data dirs wiped, then a full fresh run |
| `--purge` | deleted | deleted | deleted — and the command exits (no run) |

## `--no-llm` and stub records

`--no-llm` produces **stub records**: schema-conformant placeholders (`stubbed: true`) written so later full runs have *something* to show, and no network is touched. A full run treats a stub as a cache miss — real prose always overwrites it — while another `--no-llm` run happily reuses it. That is why you can preview a whole documentation set offline and then fill in the real prose without deleting anything.

## What never is cached

The graph build and the markdown rendering are recomputed on every run from the current records; they are cheap and must always reflect the current set of files. The doc cache, records, and symbols cache together are the only state that carries between runs.

Related: [Determinism](02%20-%20Determinism.md), [LLM Phase](05%20-%20LLM%20Phase.md), [Output and Data Formats](../04%20-%20Reference/02%20-%20Output%20and%20Data%20Formats.md).
