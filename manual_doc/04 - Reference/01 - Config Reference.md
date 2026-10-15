# Config Reference

The configuration file (`settings.yaml` by default, or `--config PATH`) is plain YAML. Relative paths resolve against the config file's own directory. Every key the pipeline actually reads is listed below with its effective default — the shipped `settings.yaml` value first, then the code fallback.

> **Honesty note:** `settings.yaml` ships with a few keys the current code does **not** consume (`project.source_extensions`, `documentation.variable_scope`, `context.include_imports`, `context.include_call_targets`, `context.include_referenced_variables`). They are listed at the end so their presence isn't a surprise; changing them has no effect today.

## project

| Key | Default | Meaning |
| --- | --- | --- |
| `source_dir` | `"."` | folder scanned for source files. |
| `output_dir` | `"docs"` | where rendered markdown is written. |
| `data_dir` | `"docs/.data"` | where `graph.json`, `symbols.json`, `diagnostics.json` are kept. |
| `exclude` | `[]` | path segments to skip (e.g. `vendor`, `generated`) — a file under any of them is skipped and reported, never fatal. |
| `max_file_bytes` | `26214400` (25 MiB) | files larger than this are skipped and reported. |
| `copy_meta` | `true` (settings) / `false` (code) | also copy the three meta JSON files into `<output_dir>/meta/` (needed for the web graph view; see [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md)). |
| `manual_doc` | (empty) | a hand-written docs folder to copy into `<output_dir>/manual` and list on the index as "Manual documentation" (see [Rendering](../02%20-%20How%20It%20Works/07%20-%20Rendering.md)). |

## llm

| Key | Default | Meaning |
| --- | --- | --- |
| `model` | — | model name sent to the API. **Always from settings** — there is no `.env` model key. |
| `base_url` | `"env"` | read from `.env` key `base_url` (project root first, then the config's directory). |
| `api_key` | `"env"` | read from `.env` key `api_key`. |
| `max_retries` | `5` | total transport attempts per call (see [LLM client](../03%20-%20Components/04%20-%20LLM%20Client.md)). |
| `temperature` | `0.1` | near-deterministic prose. |
| `max_tokens` | `900` | reply budget. |
| `timeout` | `300` | per-attempt socket timeout (seconds). |

## context

| Key | Default | Meaning |
| --- | --- | --- |
| `max_symbols_per_list` | `25` | how many functions appear in a file-summary context. |
| `max_source_lines` | `300` | body lines included in a function's context; beyond this the body is truncated and a note is added (see [Chunk and Merge](../02%20-%20How%20It%20Works/06%20-%20Chunk%20and%20Merge.md)). |

## documentation

| Key | Default | Meaning |
| --- | --- | --- |
| `generate_function_docs` | `true` | produce per-function prose. |
| `generate_variable_docs` | `true` | produce per-variable prose. |
| `generate_file_summaries` | `true` | produce per-file summaries. |
| `include_anonymous_functions` | `false` | also send `anon` (context-named) functions to the LLM phase; off by default to save tokens. |
| `max_function_lines` | `20` (settings) / `0` (code = off) | functions longer than this are documented via chunk-and-merge. |
| `chunk_target_tokens` | `20000` | target size per chunk call (budget ≈ `chunk_target_tokens × chars_per_token` characters). |
| `chars_per_token` | `4` | rough token estimate used with the budgets. |
| `max_chunk_lines` | `4000` | hard cap on chunk size in lines. |
| `retry_invalid_json` | `2` | extra attempts when the model returns malformed JSON. |
| `skip_existing` | `true` | load previously generated records and skip re-generating unchanged symbols (the record cache, see [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md)). |

## concurrency (top-level)

| Key | Default | Meaning |
| --- | --- | --- |
| `concurrency` | `2` | parallel LLM workers in the [LLM phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md). Any positive integer. |

## tui

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | show the Rich terminal panel during the LLM phase (auto-off when stdout is not a TTY). |
| `interval` | `0.5` | refresh interval (seconds). |

## prompts

| Key | Default | Meaning |
| --- | --- | --- |
| `function` | `./prompts/function.txt` | system-prompt base for function docs. |
| `chunk` | `./prompts/function_chunk.txt` | system-prompt base for chunk summaries. |
| `variable` | `./prompts/variable.txt` | system-prompt base for variable docs. |
| `summary` | `./prompts/summary.txt` | system-prompt base for file summaries. |

The [Prompts](03%20-%20Prompts.md) page documents each file and how the JSON schema is appended at call time.

## Keys present but not consumed by the current code

These appear in the shipped `settings.yaml`; the current code never reads them, so changing them has **no effect** today:

| Key | Note |
| --- | --- |
| `project.source_extensions` | the scan routes files by the extensions the backends claim (`backends.EXTRACTORS`), not by a config list. |
| `documentation.variable_scope` | the pipeline documents file-level variables; there is no scope switch in the code. |
| `context.include_imports` | no code reads this key. |
| `context.include_call_targets` | no code reads this key. |
| `context.include_referenced_variables` | no code reads this key. |

Related: [Configuration](../01%20-%20Getting%20Started/03%20-%20Configuration.md), [CLI](../03%20-%20Components/06%20-%20CLI.md).
