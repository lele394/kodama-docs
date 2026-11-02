# Prompts

The prose each page carries is produced by four prompt files (one per [LLM phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md) kind). They are plain text, live in `prompts/`, and are wired up by the `prompts` section of the config (see [Config Reference](01%20-%20Config%20Reference.md)).

## How a prompt becomes a call

At run time `generate()` (see [LLM client](../03%20-%20Components/04%20-%20LLM%20Client.md)) assembles the **system** message as:

```
<your prompt file, with {template} keys rendered>

Return ONLY one JSON object, no markdown fences, matching this schema exactly:
<the JSON schema for the kind, dumped from kodama_docs/models.py>

Field values must be plain strings. Be concise and factual.
```

The prompt file is a **template**. Before the call, kodama-docs replaces the
known `{key}` placeholders for that task (single pass; unknown braces are left
untouched, so JSON examples in custom prompts are safe). The **user** message
is the deterministic context (the symbol, its code, its callers/callees — see
[LLM Phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md) and
[Chunk and Merge](../02%20-%20How%20It%20Works/06%20-%20Chunk%20and%20Merge.md)).
The schema is embedded verbatim from code, so the model and the validator can
never disagree about the expected shape; a reply that doesn't validate is
rejected and retried (up to `documentation.retry_invalid_json` extra times).

### Template keys

| Key | Value |
| --- | --- |
| `{language}` | `Python`, `Lua`, `C`, `C++` or `CUDA` |
| `{language_family}` | `python`, `lua` or `c-family` |
| `{dialect}` | `c`, `cpp` or `cuda` |
| `{file}` | source relpath |
| `{symbol}` | qualified symbol name; file path for summaries |
| `{name}` | unqualified symbol name |
| `{kind}` | `function`, `function chunk`, `variable`, `file summary` |
| `{line}` / `{line_end}` | symbol start/end line |
| `{params}` | comma-separated parameter names |
| `{fence}` | code-fence language |
| `{developer_comment}` | glued developer comment, or empty |

The shipped prompts use `{language}` and `{file}`, so the same files work for
every backend.

## The four files

| File | Default path | Kind | Required output |
| --- | --- | --- | --- |
| `function.txt` | `./prompts/function.txt` | `function` | `description` (1–3 sentences, min 8 chars) + optional `arguments`, `outputs`, `side_effects`, `references` (≤ ~10), `uncertainties` (≤ ~5). |
| `function_chunk.txt` | `./prompts/function_chunk.txt` | `chunk` | `summary` (2–4 sentences, min 12 chars) for **one part** of a long function. |
| `variable.txt` | `./prompts/variable.txt` | `variable` | `description` (1–2 sentences, min 8 chars) + optional `notes` (≤ 16). |
| `summary.txt` | `./prompts/summary.txt` | `summary` | `summary` (2–4 sentences, min 16), `main_purpose` (1 sentence), `role` (1 sentence). |

All four share the same guardrails: **base the answer only on the visible code, never invent behavior, and put doubts in `uncertainties`** (function) / keep it factual and minimal (variable). They are language-neutral and use `{language}` to ask for the right idioms; the surrounding pipeline is language-agnostic.

## Editing them safely

- Keep the contract: the model must return **one JSON object** matching the kind's schema. The schema itself is fixed in code (`kodama_docs/models.py`), so your prompt can only *constrain the prose style*, not the shape.
- You can tighten tone, length, and which optional keys to fill — the validator will still enforce min-lengths and item caps, and reject extra keys (`additionalProperties: false`).
- If you want a different default, point the `prompts` config keys at your own files (relative paths resolve against the config's directory).

## Related

- [LLM Phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md) — what context each call sees.
- [LLM client](../03%20-%20Components/04%20-%20LLM%20Client.md) — retry and validation mechanics.
- [LLM Problems](../06%20-%20Troubleshooting/01%20-%20LLM%20Problems.md) — what invalid-JSON retries look like in the log.
