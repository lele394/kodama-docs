# kodama-docs

kodama-docs reads a source codebase and turns it into browsable, cross-linked documentation. The exact, structural parts — which files exist, what each function is, which symbols call or import which — are computed **deterministically** from the code. A local or remote LLM then writes only the human prose (summaries and explanations) around that fixed structure. The result is a static site: an `index.md`, one page per source file, and this manual.

## What this manual is

The [README](../README.md) is a quick overview. This manual is the deeper, sectioned reference: how each part of the tool works, every configuration key, each language backend, and the things that go wrong and how to fix them.

This "Manual" group is **section 0** of every build — the one place where hand-written content sits at the top of the sidebar, above the generated docs. No LLM is involved in this content.

## How it is organized

- [01 - Getting Started](01%20-%20Getting%20Started/01%20-%20Install.md) — install, your first run, configuration, serving.
- [02 - How It Works](02%20-%20How%20It%20Works/01%20-%20Overview.md) — the pipeline, determinism, the graph, chunk-and-merge, caching.
- [03 - Components](03%20-%20Components/01%20-%20Backends.md) — backends, the Lua and Python backends, the LLM client, the web server, the CLI.
- [04 - Reference](04%20-%20Reference/01%20-%20Config%20Reference.md) — every config key, the output and data formats, the prompts.
- [05 - Examples](05%20-%20Examples/01%20-%20Documenting%20a%20Lua%20Project.md) — end-to-end walkthroughs, including kodama-docs documenting itself.
- [06 - Troubleshooting](06%20-%20Troubleshooting/01%20-%20LLM%20Problems.md) — LLM, parsing, and performance problems.
- [07 - Concepts](07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md) — the symbol/graph model and a glossary.
- [08 - Contributing](08%20-%20Contributing/01%20-%20Adding%20a%20Language.md) — how to add a language and how the code is organized.
- [09 - FAQ](09%20-%20FAQ.md) — common questions.
