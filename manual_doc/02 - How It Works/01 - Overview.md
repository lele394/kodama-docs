# Overview

kodama-docs turns a source tree into a documentation site in five stages. Only the last two can involve an LLM; the first three are pure code and are fully reproducible.

## The pipeline

- **Scan** — walk `project.source_dir`, pick out the files a backend can parse, and read them. Excluded folders, unsupported extensions, and files over `project.max_file_bytes` are skipped (and reported).
- **Extract** — for each file, the matching backend's `extract(source, relpath)` produces a structured record of its functions, file-level variables, calls, and imports. See [Extraction](03%20-%20Extraction.md).
- **Graph** — those records become a directed graph: files, symbols, and the `CONTAINS`, `CALLS`, `IMPORTS`, and `READS` relationships between them, each tagged with whether it resolved. See [Graph](04%20-%20Graph.md).
- **Prose** *(optional)* — for every function, variable, and file summary, an LLM agent writes the human explanation. Skipped entirely with `--no-llm`. See [LLM Phase](05%20-%20LLM%20Phase.md).
- **Render** — `index.md`, one page per file, the graph data, and diagnostics are written to `project.output_dir`. See [Rendering](07%20-%20Rendering.md).

The stages run in that order; only the **Prose** stage can call an LLM.

## The two-layer model

The tool is deliberately split in two:

- A **deterministic core** — backends, the graph, and rendering. Given the same inputs and the same backend versions, it always produces the same structure and the same links.
- An **optional prose layer** — the LLM phase, which only adds explanations on top of that structure and never changes it.

This split is what makes the output trustworthy: the things you can verify (what exists, what calls what) never depend on a model, and the model is asked only to describe them. Details in [Determinism](02%20-%20Determinism.md).

## A typical run

```bash
python main.py --config settings.yaml            # full run (LLM included)
python main.py --config settings.yaml --no-llm   # structure only, no LLM
python main.py --config settings.yaml --serve    # browse the rendered docs
```

The command-line verbs and flags are documented in [CLI](../03%20-%20Components/06%20-%20CLI.md).
