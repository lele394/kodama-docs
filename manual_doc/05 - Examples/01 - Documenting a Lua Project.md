# Documenting a Lua project

A concrete walkthrough using the bundled Lua N-body sample at `test_codebases/lua/` (a small game-style project: `main.lua`, `physics/body.lua`, `physics/nbody.lua`, `physics/vec3.lua`). The steps are exactly what you would do for any Lua codebase.

## 1. Prepare a config

`test_codebases/lua/settings.yaml` (paths resolve against that folder):

```yaml
project:
  source_dir: "codebase"      # the Lua project root
  output_dir: "docs"          # rendered markdown lands here
  data_dir: "data"            # analysis cache + records
  exclude: []
  max_file_bytes: 26214400
  copy_meta: true             # emit meta/graph.json for the web graph view

llm:
  base_url: env               # read from .env
  api_key: env                # read from .env
  model: "your-model"
  max_retries: 5
  temperature: 0.1
  max_tokens: 900
  timeout: 300
  # …see the full [Config Reference](../04%20-%20Reference/01%20-%20Config%20Reference.md)

documentation:
  generate_function_docs: true
  generate_variable_docs: true
  generate_file_summaries: true
  max_function_lines: 20      # longer functions use chunk-and-merge
```

A `.env` next to it holds `base_url` and `api_key`.

## 2. Check that the Lua backend is ready

```bash
python main.py --list-backends
```

You want to see `kodama-lua … status=ready`. If it is `unavailable`, the `tree-sitter-lua` dependency is missing — install it (or `--install` the backend) and re-check.

## 3. Run it (offline first, then with the model)

```bash
# structure-only pass: no network, fast, shows you exactly what will be documented
python main.py --config test_codebases/lua/settings.yaml --no-llm

# full pass: real prose for every function/variable/summary
python main.py --config test_codebases/lua/settings.yaml
```

The offline pass writes the complete `docs/` set with placeholder prose and the full `data/` analysis (graph, symbols, diagnostics), so you can inspect the symbol graph before spending any tokens. The full pass fills in the prose and caches it in the record store.

## 4. Read the output

- `docs/index.md` — "N files documented", the per-file table, and the Analysis summary (how many call references resolved, how many were ambiguous/external/unresolved).
- `docs/files/main.lua.md` — one page per file. `main.lua`'s `local Body = require("physics.body")` binds `Body`, so calls to `Body:new(...)` link to the `new` definition in `physics/body.lua`. Calls through a type-unknown parameter (`sim:step(...)` in `tick`) show as `step (inferred)`, and `log.info` is orange (unresolved, because there is no `log` module in the project) — none of these are silently dropped.
- `docs/meta/graph.json` — the full graph, ready for `--serve`.

## 5. Serve it

```bash
python main.py --config test_codebases/lua/settings.yaml --serve
```

Open `http://127.0.0.1:8123` for the rendered docs and `/graph` for the interactive call graph.

## What the sample demonstrates

- **Method-call resolution across files** — `Body:new(...)` in `main.lua` links to `new` in `physics/body.lua` (`[new](physics/body.lua.md#fn-new-9)`). The [Lua backend](../03%20-%20Components/02%20-%20Lua%20Backend.md) records `Body` as the bound module (from `require("physics.body")`) and `new` as the method, so the resolver can match them.
- **Inferred references** — `sim:step(bodies, dt)` in `tick` is marked `step (inferred)`: `sim` is a plain parameter whose type the resolver can't pin to one module, so the reference is kept but not linked.
- **Unresolved references stay visible** — `log.info` is orange in the page (no link written) because there is no `log` module in the project; it is *not* silently dropped, and it shows up in the "unresolved" section and the Analysis summary.

Related: [First Run](../01%20-%20Getting%20Started/02%20-%20First%20Run.md), [Documenting kodama-docs Itself](02%20-%20Documenting%20kodama-docs%20Itself.md).
