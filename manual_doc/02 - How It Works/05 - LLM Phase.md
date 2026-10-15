# LLM phase

The LLM phase turns the fixed structure into prose. It builds a list of jobs — one per function, variable, file summary, and chunk — runs them on a pool of parallel agents, and caches each result separately. It returns how many jobs failed, and that count decides whether the run is considered complete.

## What a job is

Each job asks the model for a **JSON object** of a specific kind, validated against a schema before it is accepted:

| Kind | Describes |
| --- | --- |
| `function` | One function or method. |
| `variable` | One file-level variable. |
| `summary` | The whole file. |
| `chunk` | One part of a long function body (see [Chunk and Merge](06%20-%20Chunk%20and%20Merge.md)). |

The model receives two messages — a **system** prompt (the task and the required format) and a **user** message (the code and its context) — against an OpenAI-compatible endpoint: `POST {base_url}/chat/completions` with `{model, temperature, max_tokens, messages}`.

## The settings that shape a job

- `prompts.{function,variable,summary,chunk}` — the system prompt for each kind (see [Prompts](../04%20-%20Reference/03%20-%20Prompts.md)).
- `context.*` — how much surrounding code (imports, call targets, referenced variables) is included in each job's user message.
- `llm.temperature` (default `0.1`), `llm.max_tokens` (default `900`), `llm.timeout` (default `300` seconds).
- `concurrency` — how many agents run in parallel.

## Retries and validation

The client retries up to `llm.max_retries` times on transport errors, and the generator retries up to `documentation.retry_invalid_json` (default `2`) times when the model returns invalid JSON. A job that still fails is counted and reported, and its file still ships with placeholder prose so the build never silently loses content.

## Progress

When `tui.enabled` is set, a live view shows each file as its jobs move through the stages (chunk, then function, variable, summary). `tui.interval` sets the refresh rate.

## Skipping it

`--no-llm` runs the same job list but never calls the model: every job becomes a **stub**, cached as `stubbed`, and a later full run replaces the stubs. See [Caching](08%20-%20Caching.md).

The request shape, error handling, and the JSON validation are in [LLM Client](../03%20-%20Components/04%20-%20LLM%20Client.md).
