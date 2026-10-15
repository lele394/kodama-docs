# Chunk and merge

Long functions can outgrow a single prompt. Instead of truncating them, the LLM phase splits the body into **chunks**, asks the model to summarize each part, and then describes the whole function **synthesizing those part summaries**. Everything about the split is deterministic; only the prose is generated.

## When it kicks in

A function goes through chunk-and-merge when `documentation.max_function_lines` is set (the shipped default is `20`) **and** the function body is longer than that many lines. With `max_function_lines: 0` the feature is off and every function is described in one call, body truncated to `context.max_source_lines` (default `300`).

## How the body is split

`fn_chunks()` in `kodama_docs/context.py` is a pure function of the body and two knobs:

- `documentation.max_chunk_lines` — a hard line cap per chunk (fallback `4000`);
- `documentation.chunk_target_tokens` — a soft size budget, converted to characters with `documentation.chars_per_token` (default `20000` × `4` ≈ 80k characters).

Breaks are preferred **after top-level statements** (a line whose indent is no deeper than the body's base indent), so a chunk rarely starts in the middle of a block. If a single line exceeds the budget it is forced as its own chunk, so the splitter always makes progress. The same body with the same settings always yields the same chunks.

## The two kinds of prompts

1. **`chunk`** — for each chunk, the model receives the function's name, line span, parameters, and only that chunk's code (labeled "Body part *i*/*n* of a long function"). It must return a single JSON object: `{"summary": "…"}` (2–4 sentences, default prompt `prompts/function_chunk.txt`).
2. **`function`** — once every chunk has a summary, the function job runs **without the raw body**. Instead of the code it receives a note: "The body is long; it was summarized part by part: 1. … 2. … — Describe the WHOLE function, synthesizing these parts." The rest of the function context (name, parameters, callers, callees) is unchanged.

Each chunk summary is cached as its own record (kind `chunk`), keyed by chunk index and text, so re-runs never re-ask for a chunk that hasn't changed.

## What you see in the output

The rendered function page is identical whether or not chunking happened — the same `Description`, `Parameters`, `Outputs`, `Side effects` blocks. Chunking only changes how the prose was produced. In the TUI, a long function shows a `chunk i/n` stage followed by a `merge` stage before the job finishes.

The job list, caching, and failure handling around these calls are covered in [LLM Phase](05%20-%20LLM%20Phase.md) and [Caching](08%20-%20Caching.md); the prompt text itself is in [Prompts](../04%20-%20Reference/03%20-%20Prompts.md).
