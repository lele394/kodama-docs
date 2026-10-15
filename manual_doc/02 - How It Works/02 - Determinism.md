# Determinism

The parts of kodama-docs that you can verify — what exists, what calls what, how things are linked — are computed without any LLM. This is a design rule, not an accident: the model may add prose, but it may never change the structure.

## What is deterministic

- **Extraction** — the set of files, functions, variables, calls, and imports comes from the backend parsers reading the source text alone.
- **The graph** — the `CONTAINS`, `CALLS`, `IMPORTS`, and `READS` edges, and their resolved/unresolved status, come from the records and the resolvers.
- **Rendering** — page layout, anchors, cross-links, and call/import context are built from the graph.

Given the same inputs, the same config, and the same backend versions, these produce the same output.

## What the LLM adds (and nothing else)

Only the human explanations — function, variable, and file summaries — come from an LLM agent. They are stored separately as "records" and can be regenerated, deleted, or stubbed without touching the structure. See [LLM Phase](05%20-%20LLM%20Phase.md).

## Proving it

Run with `--no-llm` and the whole site still renders: every page, link, graph, and diagnostic is present, and only the prose is a placeholder.

```bash
python main.py --config settings.yaml --no-llm
```

That placeholder prose is marked as a **stub** in the record cache; a later full run replaces stubs but reuses any already-good prose. See [Caching](08%20-%20Caching.md).
