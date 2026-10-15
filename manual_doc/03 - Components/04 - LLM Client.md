# LLM client

`kodama_docs/llm.py` is the only code that talks to the model. It is deliberately tiny and stdlib-only (urllib), with exactly two layers: a **transport** (`LLMClient`) and a **structured generation** helper (`generate`) that enforces the JSON contract of each prompt kind.

## The transport — `LLMClient.chat(system, user)`

One `POST` to `{base_url}/chat/completions` with the OpenAI-compatible body:

```json
{
  "model": "...",            // llm.model from settings.yaml
  "temperature": 0.1,        // llm.temperature
  "max_tokens": 900,         // llm.max_tokens
  "messages": [
    {"role": "system", "content": "…"},
    {"role": "user",   "content": "…"}
  ]
}
```

Headers: `Authorization: Bearer <api_key>`, `Content-Type: application/json`, and a fixed `User-Agent`. The response is read as `choices[0].message.content`.

**Retries.** The whole request is retried up to `llm.max_retries` times (default `5`) — *total attempts*, not extra retries — on any failure (timeout, HTTP error, JSON decode failure). Each attempt is logged (`llm attempt i/5 failed: …`); when the budget is exhausted, `LLMError` is raised and the task is counted as failed (never fatal to the run — see [LLM Phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md)).

## Structured generation — `generate()`

Prompts promise *one JSON object matching a schema*. `generate(client, kind, base_prompt, user_ctx, max_invalid_retries=2, no_llm)` makes that real:

1. The schema (from `kodama_docs/models.py`, per kind `function` / `chunk` / `variable` / `summary`) is appended verbatim to the **system** prompt, along with "return ONLY one JSON object".
2. The model's reply is parsed with a balanced-brace scanner that respects strings and escapes — it does not need the JSON to start at byte 0, and it is not fooled by braces inside string values.
3. If the reply is not a valid object, the *error note* is appended to the **user** message and the call is retried — `max_invalid_retries` (default `2`, driven by `documentation.retry_invalid_json`) extra attempts, i.e. 3 total. Then `LLMError`.

So there are two independent retry budgets: transport-level (network, default 5) and shape-level (invalid JSON, default 3).

## The `--no-llm` path

`generate(..., no_llm=True)` returns a **stub object** for the kind — the exact shape the renderer expects (`description` / `summary` / `main_purpose` / `role`), marked `stubbed: true` in the record. No network, no retries, no delays. This is what makes `--no-llm` a fast, fully offline first pass that later full runs overwrite. See [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md).

## Where the settings come from

| Setting | Default | Effect |
| --- | --- | --- |
| `llm.base_url` / `llm.api_key` | `"env"` | read from `.env` (`base_url`, `api_key`) — project root first, then the config's directory. |
| `llm.model` | — | the model name; **always** from `settings.yaml` (there is no `.env` model key). |
| `llm.max_retries` | `5` | total transport attempts per call. |
| `llm.temperature` | `0.1` | near-deterministic prose. |
| `llm.max_tokens` | `900` | reply budget. |
| `llm.timeout` | `300` | per-attempt socket timeout (seconds). |
| `documentation.retry_invalid_json` | `2` | extra attempts for malformed JSON. |

Related: [LLM Phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md), [Prompts](../04%20-%20Reference/03%20-%20Prompts.md), [LLM Problems](../06%20-%20Troubleshooting/01%20-%20LLM%20Problems.md).
