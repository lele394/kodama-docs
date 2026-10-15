# Configuration

Everything is driven by one YAML file (default `settings.yaml`, override with `--config PATH`). Relative paths are resolved against the **config file's directory**, not the current working directory.

## Where each group lives

- `project` — what to read and where to write.
- `llm` — the OpenAI-compatible endpoint and its knobs.
- `context` — how much surrounding context each LLM task receives.
- `documentation` — what to generate and how to chunk long functions.
- `concurrency` — how many LLM agents run in parallel.
- `tui` — the live progress view.
- `prompts` — the per-task prompt files.

## The keys you will touch most

| Key | Default | Meaning |
| --- | --- | --- |
| `project.source_dir` | required | Folder to document. |
| `project.output_dir` | required | Where `doc/` is written. |
| `project.data_dir` | required | Cache: symbols, graph, LLM records. |
| `project.exclude` | `[]` | Folder names to skip. |
| `project.max_file_bytes` | `26214400` | Files larger than this are skipped. |
| `project.copy_meta` | `false` | Also write `meta/symbols.json`, `meta/graph.json`. |
| `project.manual_doc` | unset | A folder of hand-written pages (section 0). |
| `llm.base_url` | `env` | Endpoint, or `env` to read `.env`. |
| `llm.api_key` | `env` | Key, or `env` to read `.env`. |
| `llm.model` | — | Model name. |
| `llm.timeout` | `300` | Per-request seconds. |
| `llm.max_retries` | `5` | Retries on failure. |
| `concurrency` | `2` | Parallel LLM agents. |
| `documentation.max_function_lines` | `20` | Functions longer than this are chunked. |
| `documentation.chunk_target_tokens` | `20000` | Target size of one chunk. |
| `documentation.skip_existing` | `true` | Reuse cached prose instead of regenerating. |

## The `env` shorthand

`llm.base_url: env` and `llm.api_key: env` tell kodama-docs to read the real values from a `.env` file — looked up in the project root first, then next to the config. This keeps secrets out of the YAML.

The full, key-by-key reference lives in [Config Reference](../04%20-%20Reference/01%20-%20Config%20Reference.md).
