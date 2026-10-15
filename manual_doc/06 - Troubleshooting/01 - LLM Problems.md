# LLM problems

The LLM phase is the only part of a run that talks to the network. Everything it does is retried, logged, and resumable — but when it does fail you get exit code **1** (docs are still written, with placeholder prose) and a clear log trail. This page maps the symptoms to causes.

## "llm attempt N/5 failed" then "LLM call failed after retries"

This is a **transport** failure — the request never produced a usable reply. Each line is one of the `llm.max_retries` (5) attempts.

- **Wrong `base_url`.** The client POSTs to `{base_url}/chat/completions` (OpenAI-style). If you point it at a root that already ends in `/v1/chat/completions` or at a non-OpenAI endpoint, every attempt 404s. `base_url` should be the API root, e.g. `http://127.0.0.1:11434/v1`.
- **Missing / bad `api_key`.** Both `base_url` and `api_key` are read from `.env` (project root first, then the config's directory; keys are lowercased, quotes stripped). There is **no model key in `.env`** — the model always comes from settings.
- **Network / timeout.** Per-attempt socket timeout is `llm.timeout` (default 300 s). A cold model load on the first request can exceed this; raise it for local servers.
- **Model name.** `llm.model` is passed verbatim. A typo here usually surfaces as an HTTP 400/404 from the provider.

## "invalid JSON after 2 retries"

The model answered, but its reply didn't validate against the kind's schema (see [Prompts](../04%20-%20Reference/03%20-%20Prompts.md)). The `generate()` loop gives the model up to `documentation.retry_invalid_json` (2) **extra** attempts after the first, appending the specific error ("no JSON object found", "missing required key …", "string shorter than N chars", "unknown key …") back to it.

Common causes and fixes:

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| reply truncated mid-sentence | `llm.max_tokens` (900) too small for the requested fields | raise `max_tokens`; the validator will accept a complete object |
| markdown fences around the JSON | model ignoring "return ONLY one JSON object" | the code already strips/scans for a balanced brace object — usually a weak model; try a stronger one or lower `temperature` |
| extra keys / wrong shape | model inventing fields | fixed by the prompt + schema; a different model usually behaves |

## A task failed but the run "succeeded"

If **any** task fails, the run ends with exit code **1**, logs:

```
NOT updating .doc_cache (N failed task(s) this run; unchanged cached records still reused next time)
```

and the affected pages carry placeholder prose. This is intentional (P0-3: failures must stay visible):

- Saved records from earlier in the run are **kept**, so a rerun picks up where it left off — unchanged symbols are reused from the record cache and only the failed ones are retried.
- `.doc_cache` is only written when there were **zero** failures, so the next run won't mark a partial result as "current".
- `--no-llm` writes `stubbed: true` records; a later **full** run treats those as cache misses and overwrites them with real prose (a `--no-llm` run may reuse them).

## Interrupted runs (Ctrl-C)

```
interrupted by user — saved docs and records kept; .doc_cache not updated; rerun to continue where it left off
```

Exit code 130. In-flight tasks (at most `concurrency` of them) finish and save; queued work is cancelled. Just rerun.

## Verifying your endpoint without the pipeline

The fastest way to separate "my model is misbehaving" from "kodama-docs bug" is a raw `curl` to the same `{base_url}/chat/completions` with the same `model` and a small `max_tokens`. If that returns valid JSON and the pipeline doesn't, it's the shape/length of the request — see the [LLM client](../03%20-%20Components/04%20-%20LLM%20Client.md) for the exact request body.

Related: [Config Reference](../04%20-%20Reference/01%20-%20Config%20Reference.md), [First Run](../01%20-%20Getting%20Started/02%20-%20First%20Run.md).
