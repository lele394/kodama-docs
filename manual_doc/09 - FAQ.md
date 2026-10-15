# FAQ

Quick answers, with a link to the page that has the full detail.

**What does it actually produce, and what part is AI-generated?**
Deterministic structure: the file tree, per-file pages, cross-reference links, tables, the graph, and `index.md`. AI-generated: the prose descriptions (function/variable/summary text) — that's the only thing an LLM writes. See [Determinism](02%20-%20How%20It%20Works/02%20-%20Determinism.md) and [LLM Phase](02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md).

**Does it modify my source code?**
No. It only reads your sources and writes to `project.output_dir` (docs + `meta/`), `project.data_dir` (LLM records), and the `.doc_cache` file inside the output dir. Nothing in the tree is edited.

**What's the difference between `--no-llm` and a normal run?**
`--no-llm` runs the entire pipeline with placeholder prose instead of LLM calls — real structure and links, no network, no token cost, and it never writes a record that a later full run would consider valid. A normal run asks the model for prose (reusing the cache where possible). Use `--no-llm` to iterate on structure fast; see [First Run](01%20-%20Getting%20Started/02%20-%20First%20Run.md) and [Performance](06%20-%20Troubleshooting/03%20-%20Performance.md).

**Why are some references orange or labeled `(inferred)`?**
Those are references the resolver could not tie to a single project definition. `inferred` = the name is defined exactly once project-wide but wasn't import-bound; orange = a builtin/stdlib or an out-of-project (external) name; an **ambiguous** name (defined 2+ times) gets *no* link at all and is recorded in `diagnostics.json`. The tool never guesses. See [Symbols and Graph](07%20-%20Concepts/01%20-%20Symbols%20and%20Graph.md) and [Parsing and Resolution](06%20-%20Troubleshooting/02%20-%20Parsing%20and%20Resolution.md).

**Why aren't my anonymous functions documented?**
They are in the graph and rendered, but excluded from the LLM phase by default to save tokens. Set `documentation.include_anonymous_functions: true` to have their prose generated too. See [Config Reference](04%20-%20Reference/01%20-%20Config%20Reference.md).

**Why doesn't a re-run hit the LLM cache for a symbol I didn't change?**
A record is only reused if its fingerprint matches. The fingerprint covers the symbol's source **and its callers/callees**, plus the model, base URL, prompt text, and the shaping settings. So changing a function's *callers*, changing the model, editing a prompt, or changing the relevant knobs invalidates the cached record. See [Caching](02%20-%20How%20It%20Works/08%20-%20Caching.md) and [Code Organization](08%20-%20Contributing/02%20-%20Code%20Organization.md) (`tasks.py` holds the fingerprint definitions).

**What's the difference between `--regenerate` and `--purge`?**
Both delete the output/data dirs and start clean. `--regenerate` deletes **and runs** the pipeline; `--purge` deletes **and exits**. They are mutually exclusive. See [CLI](03%20-%20Components/06%20-%20CLI.md).

**Does it only work with Lua and Python?**
No — those are the bundled backends. The pipeline is language-agnostic: add a backend package (or `--install URL` an external one) that claims a new extension, and its files are documented. See [Adding a Language](08%20-%20Contributing/01%20-%20Adding%20a%20Language.md) and [Backends](03%20-%20Components/01%20-%20Backends.md).

**Where is my API key, and what's it sent to?**
`llm.api_key` and `llm.base_url` are taken from the config, but the literal value `"env"` (or a missing value, the default) means "read it from a `.env` file" — searched project-root-first (next to `main.py`), then the config file's directory. If `env` is required but the key isn't found, the run stops with a clear message listing the paths it looked in. The key is only ever sent as a Bearer token to `llm.base_url` — the endpoint you configure (often a local model server). Nothing else leaves the machine except the LLM calls you initiate. See [LLM Client](03%20-%20Components/04%20-%20LLM%20Client.md).

**My run ended with exit code 1. Is that a crash?**
No. Exit 1 means at least one LLM task failed and `.doc_cache` was not updated. Saved records are kept; rerunning resumes where it left off (failed tasks are retried). A *hang* or a Ctrl-C is different (Ctrl-C exits 130 and also keeps progress). See [LLM Problems](06%20-%20Troubleshooting/01%20-%20LLM%20Problems.md).

**How do I preview the generated docs in a browser?**
`python main.py --serve` starts the web app (default `127.0.0.1:8123`) with the docs, a file sidebar, a fuzzy search, and the interactive graph. See [Web Server](03%20-%20Components/05%20-%20Web%20Server.md).

**Can I document this tool itself?**
Yes — it's a Python project and its own backend documents it. `configs/self.yaml` + `doc_self/` are the committed self-documentation. See [Documenting kodama-docs Itself](05%20-%20Examples/02%20-%20Documenting%20kodama-docs%20Itself.md).

**What license, and can the output be used to train a model?**
The code is MIT *with an explicit clause excluding its use as AI/ML training data*. Review `LICENSE` before reuse.

Related: [Glossary](07%20-%20Concepts/02%20-%20Glossary.md), [How It Works: Overview](02%20-%20How%20It%20Works/01%20-%20Overview.md).
