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

- **Python:** Main application and file processing.
- **LangChain:** LLM interface and prompt templates.
- **LangGraph:** Workflow states and transitions.
- **Lua parser:** Tree-sitter Lua or an equivalent parser for static analysis.
- **NetworkX:** In-memory dependency graph.
- **Pydantic:** Validation of structured LLM outputs.
- **PyYAML:** Load configuration from `settings.yaml`.
- **OpenAI-compatible API:** Connect to a local/remote inference server.

Run only one LLM task at a time. Keep function tasks independent so that parallel execution can be added later.

## 3. Directory structure

```text
lua-doc-agent/
├── settings.yaml
├── main.py
├── analyzer.py
├── graph.py
├── documentation.py
├── models.py
├── prompts/
│   ├── function.txt
│   └── summary.txt
├── src/                    # Target repository
├── data/
│   ├── symbols.json
│   ├── graph.json
│   └── functions/          # Intermediate function records
└── doc/                    # Generated documentation
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

prompts:
  function: "./prompts/function.txt"
  summary: "./prompts/summary.txt"
```

The values are initial defaults, not fixed requirements. Validate the configuration at startup. Do not hard-code prompts, model settings, or directory paths in the application.

Keep API credentials configurable. Do not log secrets.

## 5. Static analysis and code graph

This part is deterministic and should be not be done with an LLM.

Scan the source directory recursively. Process eligible Lua files only. Ignore packed binaries and excluded directories.

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

- Support Lua source files only.
- Use one local LLM endpoint.
- Execute one LLM task at a time.
- Do not modify source files.
- Do not process packed binaries.
- Do not use generated sibling documentation as function context.
- Save intermediate JSON so that completed work is not lost.
- Keep prompts and runtime settings external to the application.
- Do not implement a web interface, distributed workers, automated source modification, or advanced incremental updates in this version.

The first objective is to determine whether static analysis plus isolated LLM tasks can produce useful documentation for a real Lua codebase with acceptable context size and inference time.