# Adding a language

A language backend is a **self-contained package** inside `backends/`. The pipeline is language-agnostic: it routes each file to the backend that claims its extension and consumes a fixed shape. The authoritative contract is `backends/backend_design.md` in the repository — this page is the manual-level summary of it.

```
backends/<dir>/
    manifest.toml   # identity, capabilities, requirements
    __init__.py     # extract() (+ optional BUILTIN_NAMES, module_candidates)
```

A new backend is live the moment its directory exists and its requirements are met — there is no registry line to add.

## 1. The manifest (`manifest.toml`)

```toml
[backend]
name = "kodama-clang"                     # required, [a-z0-9][a-z0-9_-]*
description = "Kodama C backend built on clang"   # required
source = "https://github.com/you/kodama-clang"    # optional
version = "0.1.0"                        # required (arbitrary string)
api_version = "1"                        # required; this registry supports "1"

[capabilities]
languages = ["c", "cpp", "cuda"]         # optional, informational
extensions = [".c", ".cpp", ".cc", ".cu"]  # required; the routing keys
symbols = true                           # optional bools (metadata today)
references = true
call_graph = true
types = false

[requirements]
executables = ["clang"]                  # optional; each must be on PATH
python = ["clang-libs==1.8"]             # optional pip specs (import-checked)
```

- **`extensions` is required** — it is how the scan decides which files to route to you.
- Two backends claiming the **same `name` or the same extension** put **both** into `conflict` status: neither routes (no silent shadowing).
- **`api_version`** must be in the registry's supported set (currently `"1"`); a mismatched version is refused with a clear message instead of silently emitting a shape the pipeline doesn't understand.
- **`requirements`** are checked at load: each `executables` entry via `shutil.which`, each `python` spec for importability (PEP 503 normalized: `tree-sitter` → `tree_sitter`). Unmet requirements mark the backend `unavailable` — the other backends keep working.

## 2. The `extract()` contract

```python
def extract(source: str, relpath: str) -> dict: ...
```

Returns a dict with these keys (names and shapes must not change — the render, graph, and LLM-context layers depend on them):

- **`functions`** — list of `{id, name, qualified, line, end_line, params, vararg, body, developer_comment}`.
- **`file_vars`** — list of `{name, line, init}` where `init ∈ {empty, table, string, number, function, call, expr}`.
- **`calls`** — list of `{callee, line, method}`. Method calls split into `callee` + `method`; `callee` is `None` when the receiver is computed at runtime (still recorded so the reference stays visible and classifies as external).
- **`imports`** — list of `{module, line, bind, name, level}`.
- **`classes`** — list of `{name, qualified, line, end_line}` (optional for languages without classes).

### Invariants the pipeline relies on

- **1-based line numbers** — `line` and `end_line` index into the same `source` passed to `extract()`.
- **Exact body** — `body` must be exactly `source.splitlines()[line-1:end_line]` joined with `\n`; the render layer slices by these lines.
- **Document order** — lists in source order; output must be deterministic for identical input.
- **Per file** — one file at a time; cross-file links are resolved later by `graph.py`. Do not open other files.
- **No exceptions for unnameable constructs** — skip them, don't raise (a raise aborts that file's analysis).
- **Definitions are kept, not collapsed** — a name defined more than once yields one record per definition (keyed by name+line). The resolver disambiguates call sites by scope. Do not dedupe redefinitions away.
- **Dedup is by identity** — the same (name, line) is never recorded twice.
- **File vars: one record per name** (first assignment wins); class attributes must not leak into `file_vars`.

### Optional module-level exports

- **`BUILTIN_NAMES: set[str]`** — names that are *not* cross-file links (builtins, stdlib, `self`/`cls`). Without it, every undefined name becomes a dangling edge.
- **`module_candidates(module, relpath) -> list[str]`** — the relpaths a language import of `module` could resolve to. Without it the registry falls back to `<module><ext>` and `<module>/init<ext>` (plus the dotted→path form).
- **Comment-glue helpers** — use `backends/_shared.py`'s `_all_comments` and `_dev_comment` so `developer_comment` behaves identically across languages.

## 3. Ship steps

1. Create `backends/<lang>/__init__.py` with `extract()` (and optionally `BUILTIN_NAMES`, `module_candidates`).
2. Add `backends/<lang>/manifest.toml` — declare `name`, `version`, `api_version = "1"`, `extensions`, and `requirements`.
3. Make its requirements available (`pip install` the python specs; executables on PATH).
4. `python main.py --list-backends` → status `ready`. Done — the pipeline picks up its files automatically.

## External backends

```bash
python main.py --install <git-url>   # clone into backends/<name>/, pip-install its deps, report status
python main.py --remove <manifest-name>
```

> **Trust note (from the contract):** installing a backend runs third-party code at import time and `pip install`s whatever it declares — the same trust decision as any dependency. Review the backend repo before `--install`.

## Reference implementations

`backends/lua/__init__.py` (tree-sitter-lua) and `backends/python/__init__.py` (tree-sitter-python) are the reference implementations. Both use `tree-sitter` (pinned in `requirements.txt` and re-declared in their manifests) and the `_shared.py` comment-glue helpers. **No hand-rolled tokenizers.** A language-agnostic self-test harness lives in `kodama_docs/testing.py` (run it with `test-backend --backend <name>`): a backend that implements the `collect_truth()` / `parse_markers()` protocol can check its extraction against the fixture's `# expect:` markers — the Python backend implements it (249/249), the Lua backend does not. It's an optional extra, not required to route.

Related: [Backends](../03%20-%20Components/01%20-%20Backends.md), [Lua Backend](../03%20-%20Components/02%20-%20Lua%20Backend.md), [Python Backend](../03%20-%20Components/03%20-%20Python%20Backend.md), [Code Organization](02%20-%20Code%20Organization.md).
