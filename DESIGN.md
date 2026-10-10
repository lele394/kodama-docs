# Lua Codebase Documentation Agent

## 1. Objective

Build a small Python application that generates documentation for a Lua codebase using a local LLM through an OpenAI-compatible API.

The system must:

- Analyse Lua source files and build a codebase dependency graph.
- Extract functions, arguments, variables, imports, and function calls.
- Generate documentation for each function independently.
- Provide relevant graph neighbours as context to each function-documentation task.
- Generate a summary for each file after its function documentation is complete.
- Export structured JSON and readable Markdown.
- Keep prompts and runtime settings in `settings.yaml`.

The initial version is experimental. Keep the implementation small and avoid unnecessary abstractions.

## 2. Technology

- **Python 3.14:** Main application and file processing (runtime venv `.venv314`;
  tree-sitter has no cp315 wheel yet, so the 3.15 default interpreter is not
  used).
- **tree-sitter:** Parsing is fully delegated to tree-sitter grammars
  (`tree-sitter` + `tree-sitter-lua`). The project itself contains no
  tokenizer or parser; it only walks concrete syntax trees.
- **NetworkX:** In-memory dependency graph.
- **ruamel.yaml:** Load configuration from `settings.yaml`.
- **OpenAI-compatible API:** Connect to a local/remote inference server via a
  small hand-rolled HTTP client (no LangChain/LangGraph/Pydantic — the codebase
  stays small; LLM JSON is validated by a plain schema check with retries).

Run only one LLM task at a time. Keep function tasks independent so that parallel execution can be added later.

## 3. Directory structure

```text
doc_maker/
├── settings.yaml           # + settings_test.yaml
├── main.py                 # pipeline: scan -> extract -> graph -> LLM -> markdown
├── backends/
│   ├── __init__.py         # registry: file extension -> extract(source, relpath)
│   └── lua.py              # tree-sitter-lua extraction backend
├── models.py               # output schemas + deterministic JSON validator
├── graph.py                # networkx MultiDiGraph builder
├── documentation.py        # LLM client, record cache, markdown rendering
├── prompts/
│   ├── function.txt
│   ├── variable.txt
│   └── summary.txt
├── src/                    # Target repository (configured)
├── data/
│   ├── symbols.json
│   ├── graph.json
│   └── functions|variables|summaries/   # Intermediate LLM records
└── doc/                    # Generated documentation (+ doc/meta for graph data)
```

The target repository path and output paths must be configurable. The target source tree is read-only.

## 4. Configuration

All runtime settings and prompts must be configurable without changes to Python code.

Example `settings.yaml`:

```yaml
project:
  source_dir: "./src"
  output_dir: "./doc"
  data_dir: "./data"
  source_extensions: [".lua"]
  exclude:
    - "vendor"
    - "generated"
    - "packed"
    - "bin"

llm:
  base_url: "http://localhost:11434/v1"
  api_key: "ollama"
  model: "qwen3.8:27b-mtp-q4_K_M"
  max_retries: 5
  temperature: 0.1
  max_tokens: 8192
  timeout: 300

analysis:
  parser: "tree-sitter"
  extract_functions: true
  extract_variables: true
  extract_imports: true
  extract_calls: true

context:
  include_imports: true
  include_call_targets: true
  include_referenced_variables: true
  max_neighbor_files: 5
  max_context_tokens: 100000

documentation:
  generate_function_docs: true
  generate_variable_docs: true
  generate_file_summaries: true
  retry_invalid_json: 2
  skip_existing: false
  # functions over max_function_lines lines use chunk-and-merge:
  # chunk_target_tokens x chars_per_token = per-chunk input budget (chars),
  # max_chunk_lines = hard line cap per chunk
  max_function_lines: 20
  chunk_target_tokens: 20000
  chars_per_token: 4
  max_chunk_lines: 4000

# how many parallel LLM agents run the task queue (any positive integer)
concurrency: 2

# local agent dashboard served while the LLM phase runs
dashboard:
  enabled: true
  host: "127.0.0.1"
  port: 3090

prompts:
  function: "./prompts/function.txt"
  summary: "./prompts/summary.txt"
```

The values are initial defaults, not fixed requirements. Validate the configuration at startup. Do not hard-code prompts, model settings, or directory paths in the application.

Keep API credentials configurable. Do not log secrets.

## 5. Static analysis and code graph

This part is deterministic and should be not be done with an LLM.

Scan the source directory recursively. Process files whose extension has a
registered extraction backend. Ignore packed binaries and excluded directories.

**Parsing lives in per-language backends, not in this project.** Each backend
(`backends/<lang>.py`) wraps a tree-sitter grammar and projects the concrete
syntax tree into one common, language-agnostic shape consumed by the rest of
the pipeline:

```text
{'functions': [...], 'file_vars': [...], 'calls': [...], 'imports': [...]}
```

Supporting a new language = one new backend module + its tree-sitter grammar
package + one registry line in `backends/__init__.py`. Nothing in
`main.py`, `graph.py`, or `documentation.py` is Lua-specific (the Lua builtin
name set lives with the Lua backend).

Parse each file and extract:

- File paths and imports.
- Function definitions, names, arguments, and source locations.
- Local and global variables.
- Function calls and known symbol references.
- Module exports and return statements where they can be identified.

Build a directed graph with file and symbol nodes.

Use these relationships:

- `IMPORTS`: File to imported module.
- `DEFINES`: File to function or variable.
- `CALLS`: Function to called function.
- `READS`: Function to referenced variable.
- `WRITES`: Function to modified variable.
- `REFERENCES`: Reference to a known or unresolved symbol.

Resolve imports and symbols where possible. Preserve unresolved references instead of guessing their targets.

Save the graph and extracted source facts as JSON. The graph must be reusable without repeating static analysis.

## 6. Function documentation

Create one independent documentation task for every extracted function.

Each task receives:

1. The target function's source code.
2. Its exact name, arguments, source location, and known return statements.
3. Relevant module-level declarations.
4. Selected graph neighbours, such as imported modules, called functions, and referenced variables.
5. The function documentation prompt and output schema.

Each task must generate its result from these inputs alone. It must not receive generated documentation from sibling functions or other unfinished tasks.

The task must document:

- Function name and identifier.
- Input arguments and their purpose.
- Output values and their purpose.
- Description of the function's behaviour.
- Relevant side effects and dependencies.
- References to related source symbols.
- Uncertainties where the source does not establish a fact.

Use the source code as the primary authority. Do not invent types, return values, or behaviour. Represent unknown information explicitly.

Validate every result against a structured schema. Retry invalid JSON according to the configuration. Store each successful result separately, keyed by a stable symbol identifier.

**Long functions: chunk-and-merge.** Functions longer than
`max_function_lines` are not skipped. Their body is split deterministically
into chunks (statement-aligned breaks, at most `max_chunk_lines` lines and
~`chunk_target_tokens` x `chars_per_token` chars each). Each chunk gets one
small LLM task producing a short summary (cached by the chunk text's hash, so
re-runs only re-run changed chunks). One merge task then writes the standard
function record from the signature plus the chunk summaries, so the rendered
page is indistinguishable from a normally-sized function. All chunk
boundaries, ids, and ordering are deterministic; the LLM only writes prose.

## 7. Variable documentation

Generate documentation for module-level and other selected variables.

For each variable, record its name, scope, source location, inferred purpose, and relevant references.

Use static analysis to determine scope and references. Use the LLM only to explain the variable's purpose from available source context.

Avoid documenting every temporary local variable by default. The extraction policy must be configurable.

## 8. File summaries

Generate a summary only after the function and variable documentation for the file is complete.

Provide the summary task with:

- The file path and module structure.
- Imports and exports.
- Function and variable names.
- Completed documentation records.
- Important relationships with other files.

The summary must explain the file's main purpose and its role in the codebase. It must not repeat every function description.

Store the summary in the file's JSON record.

## 9. Output formats

### JSON

Store one file-level record per source file, with nested function and variable documentation.

Example:

```json
{
  "path": "src/core/main.lua",
  "summary": "Initializes the server.",
  "functions": [
    {
      "id": "src/core/main.lua::initialize",
      "name": "initialize",
      "source": {
        "start_line": 10,
        "end_line": 25
      },
      "arguments": [
        {
          "name": "config",
          "description": "Server configuration."
        }
      ],
      "outputs": [],
      "description": "Initializes the server from the supplied configuration.",
      "references": []
    }
  ],
  "variables": []
}
```

This is an illustrative record. The actual schema must also support multiple return values, unknown outputs, and unresolved references.

### Markdown

Generate Markdown from validated JSON, not directly from LLM-generated Markdown.

Preserve the source hierarchy relative to the configured source directory:

```text
src/core/main.lua       -> doc/core/main.md
src/mods/mod.lua        -> doc/mods/mod.md
src/core/utils.lua      -> doc/core/utils.md
```

Each Markdown document must contain:

1. File title.
2. File summary.
3. Function documentation.
4. Variable documentation, where enabled.
5. Links to related documentation.

Use relative Markdown links and stable function anchors. Resolve links from symbol identifiers through a deterministic symbol-to-documentation index.

## 10. Workflow

Implement the application as a LangGraph state machine:

```text
START
  |
  v
SCAN_FILES
  |
  v
PARSE_SOURCE
  |
  v
BUILD_GRAPH
  |
  v
SAVE_ANALYSIS
  |
  v
DOCUMENT_FUNCTIONS
  |
  v
DOCUMENT_VARIABLES
  |
  v
SUMMARIZE_FILES
  |
  v
RENDER_MARKDOWN
  |
  v
END
```

The function-documentation state iterates over independent tasks. Each task builds its own context, calls the LLM, validates its output, and stores the result.

Use deterministic Python code for scanning, parsing, graph traversal, validation, path mapping, and Markdown rendering. Use the LLM only for semantic descriptions and summaries.

## 11. Initial scope and constraints

- Support Lua source files for now; the pipeline is language-agnostic and new
  languages are added as tree-sitter backends (see section 5).
- Use one local LLM endpoint.
- Execute LLM tasks concurrently on a configurable pool of worker threads
  (default 2, see section 12).
- Do not modify source files.
- Do not process packed binaries.
- Do not use generated sibling documentation as function context.
- Save intermediate JSON so that completed work is not lost.
- Keep prompts and runtime settings external to the application.
- Do not implement distributed workers, automated source modification, or advanced incremental updates in this version. (A local single-machine dashboard is the exception; see section 12.)

The first objective is to determine whether static analysis plus isolated LLM tasks can produce useful documentation for a real Lua codebase with acceptable context size and inference time.

## 12. Concurrency and agent dashboard

The LLM phase builds one flat job list (functions, then variables, then file
summaries, in the same deterministic order as before) and runs it on a
`ThreadPoolExecutor` with `concurrency` workers (default 2, any positive
integer). The LLM client is stateless and each job writes a record file that
no other job touches, so no cross-job locking is needed; console logging is
guarded by a lock.

While the LLM phase runs, `dashboard.py` serves a small local page
(stdlib `http.server` only) on `dashboard.host:dashboard.port`
(default `127.0.0.1:3090`). If the port is already taken it binds an
OS-assigned port and prints the actual URL; if no server can be started at
all, the run continues without the UI. The page shows, per agent, the file
and symbol it is working on, the current stage (`chunk i/n`, `merge`,
`describe`) and time on the task / since start; at the bottom, a progress
bar, a done/total counter with generated/skipped/failed breakdown, the
average time per task and an ETA. The page polls `/status` once per second.