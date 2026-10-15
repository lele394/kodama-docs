# Prompts

The prose each page carries is produced by four prompt files (one per [LLM phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md) kind). They are plain text, live in `prompts/`, and are wired up by the `prompts` section of the config (see [Config Reference](01%20-%20Config%20Reference.md)).

## How a prompt becomes a call

At run time `generate()` (see [LLM client](../03%20-%20Components/04%20-%20LLM%20Client.md)) assembles the **system** message as:

```
<your prompt file, verbatim>

Return ONLY one JSON object, no markdown fences, matching this schema exactly:
<the JSON schema for the kind, dumped from kodama_docs/models.py>

Field values must be plain strings. Be concise and factual.
```

The **user** message is the deterministic context (the symbol, its code, its callers/callees — see [LLM Phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md) and [Chunk and Merge](../02%20-%20How%20It%20Works/06%20-%20Chunk%20and%20Merge.md)). The schema is embedded verbatim from code, so the model and the validator can never disagree about the expected shape; a reply that doesn't validate is rejected and retried (up to `documentation.retry_invalid_json` extra times).

## The four files

| File | Default path | Kind | Required output |
| --- | --- | --- | --- |
| `function.txt` | `./prompts/function.txt` | `function` | `description` (1–3 sentences, min 8 chars) + optional `arguments`, `outputs`, `side_effects`, `references` (≤ ~10), `uncertainties` (≤ ~5). |
| `function_chunk.txt` | `./prompts/function_chunk.txt` | `chunk` | `summary` (2–4 sentences, min 12 chars) for **one part** of a long function. |
| `variable.txt` | `./prompts/variable.txt` | `variable` | `description` (1–2 sentences, min 8 chars) + optional `notes` (≤ 16). |
| `summary.txt` | `./prompts/summary.txt` | `summary` | `summary` (2–4 sentences, min 16), `main_purpose` (1 sentence), `role` (1 sentence). |

All four share the same guardrails: **base the answer only on the visible code, never invent behavior, and put doubts in `uncertainties`** (function) / keep it factual and minimal (variable). The prompts are phrased for Lua source from a game installation (the project's primary target), but the surrounding pipeline is language-agnostic.

## Editing them safely

- Keep the contract: the model must return **one JSON object** matching the kind's schema. The schema itself is fixed in code (`kodama_docs/models.py`), so your prompt can only *constrain the prose style*, not the shape.
- You can tighten tone, length, and which optional keys to fill — the validator will still enforce min-lengths and item caps, and reject extra keys (`additionalProperties: false`).
- If you want a different default, point the `prompts` config keys at your own files (relative paths resolve against the config's directory).

## Related

- [LLM Phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md) — what context each call sees.
- [LLM client](../03%20-%20Components/04%20-%20LLM%20Client.md) — retry and validation mechanics.
- [LLM Problems](../06%20-%20Troubleshooting/01%20-%20LLM%20Problems.md) — what invalid-JSON retries look like in the log.
