# Documenting kodama-docs itself

The repository ships a "dogfooding" setup: `configs/self.yaml` points kodama-docs at its own Python sources and embeds the hand-written `manual_doc/` (the manual you are reading) as a section. The committed result is the `doc_self/` tree. This page shows how that works and what to look for.

## The config — `configs/self.yaml`

```yaml
project:
  source_dir: ".."            # the repo root (the config lives in configs/)
  output_dir: "../doc_self"   # rendered docs
  data_dir: "../data_self"    # analysis cache + records
  source_extensions: [".py"]  # (inert key — see below)
  exclude:
    - ".git"
    - ".venv"
    - "data"
    - "data_self"
    - "doc"
    - "doc_self"
    - "test_out"
    - "manual_doc"            # the manual is data, not code — never scan it
  copy_meta: true             # emit meta/graph.json for the web graph view
  manual_doc: "../manual_doc" # embed this manual as section 0

llm:
  base_url: env
  api_key: env
  model: "your-model"
  # …
concurrency: 4                # more agents than the default 2 (bigger project)
```

> `source_extensions` is one of the [keys the code does not consume](../04%20-%20Reference/01%20-%20Config%20Reference.md) — the scan routes by the extensions the backends claim. Listing `.py` here is harmless; it is the *Python backend* being `ready` that actually makes `.py` files get extracted.

## Running it

```bash
# structure-only pass (what doc_self/ currently is — placeholder prose)
python main.py --config configs/self.yaml --no-llm

# full pass (real prose for all 89 files)
python main.py --config configs/self.yaml
```

## Reading `doc_self/`

- **`doc_self/index.md`** — starts with a **"Manual documentation"** table that lists every page of `manual_doc/` (because `manual_doc` is set), then "89 files documented.", the per-file table, and the Analysis summary. The manual pages are links to `manual/…`, which is the verbatim copy of this folder.
- **`doc_self/files/kodama_docs/llm.py.md`** — a generated page for one of the source files. Even in the committed `--no-llm` run you can see the full deterministic structure: the function table, each function's parameters, its *References* (with orange spans for things like `cfg.get` that can't be resolved to a project symbol), and the exact source body. A full run replaces the "No description generated (`--no-llm`)" placeholders with real prose.
- **`doc_self/meta/graph.json`** — the call/reference graph of the whole project; `--serve` renders it at `/graph`.
- **`doc_self/manual/`** — the manual, copied in so its relative links and assets resolve under the docs root.

## Why this is a good example

- It exercises the **Python backend** on a real, non-trivial codebase (not just the bundled fixture).
- It shows the **manual embedding** feature end to end: `manual_doc/` → copied to `doc_self/manual/` → surfaced as the index's first table and the web sidebar's top group.
- It demonstrates that the tool can document **itself**, including its own backends, resolver, and LLM client — so the manual's claims about the pipeline are directly verifiable against the generated pages.
- The `exclude` list is the working pattern for keeping generated artifacts (`doc_self`, `data_self`), third-party code (`.venv`), and the manual itself out of the analysis.

Related: [Documenting a Lua Project](01%20-%20Documenting%20a%20Lua%20Project.md), [Python Backend](../03%20-%20Components/03%20-%20Python%20Backend.md), [Rendering](../02%20-%20How%20It%20Works/07%20-%20Rendering.md).
