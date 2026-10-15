# First run

This is the shortest path from install to a browsable documentation site. It uses `--no-llm`, so no LLM or `.env` is required — you still get the full structural docs (files, symbols, call/import graph, cross-links) with placeholder prose.

## 1. Write a minimal config

`settings.yaml` (paths are resolved against this file's directory):

```yaml
project:
  source_dir: "./my_project"      # the code to document
  output_dir: "./doc"             # rendered docs land here
  data_dir: "./data"              # analysis cache + LLM records
  copy_meta: true                 # include meta/symbols.json etc.

llm:
  base_url: env                   # ignored under --no-llm
  api_key: env
  model: "your-model"

documentation:
  generate_function_docs: true
  generate_variable_docs: true
  generate_file_summaries: true
```

## 2. Run the pipeline (deterministic only)

```bash
python main.py --config settings.yaml --no-llm
```

This scans `source_dir`, parses every supported file, builds the symbol graph, and renders `output_dir/`. You should see:

- `doc/index.md` — the overview, linking every file.
- `doc/files/<path>.md` — one page per source file, with their summaries and call/import context.
- `doc/manual/...` — this manual, if `project.manual_doc` is set.

## 3. Serve it (optional)

```bash
python main.py --config settings.yaml --serve
```

Open the URL it prints (loopback by default). You get the sidebar, search, the per-file pages, and the call-graph view at `/graph`.

## 4. Add real prose when you're ready

Put a real `.env` in place (see [Install](01%20-%20Install.md)), remove `--no-llm`, and re-run. The deterministic parts are cached, so only the missing prose is generated.

See [Configuration](03%20-%20Configuration.md) and [Serving](04%20-%20Serving.md).
