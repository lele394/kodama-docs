# Backend design contract

This is the contract every language backend must satisfy. The pipeline is
language-agnostic: it scans files, routes each file to the backend that
claims its extension (via `backends/__init__.py`), and consumes a
**fixed, language-agnostic shape**.

A backend is a **self-contained package** inside `backends/`:

```
backends/<dir>/
    manifest.toml   # identity, capabilities, requirements
    __init__.py     # extract() (+ optional BUILTIN_NAMES, module_candidates)
```

`main.py --list-backends` shows what is installed; `--install URL` adds a
backend from a git repo; `--remove NAME` deletes one. A new manifest is
live the moment its directory exists and its requirements are met — no
registry line to add.

## manifest.toml

```toml
[backend]
name = "kodama-clang"                     # required, [a-z0-9][a-z0-9_-]*
description = "Kodama C backend built on clang"   # required
source = "https://github.com/you/kodama-clang"    # optional (repo origin)
version = "0.1.0"                        # required (arbitrary string)
api_version = "1"                        # required; this registry supports "1"

[capabilities]
languages = ["c", "cpp", "cuda"]         # optional, informational
extensions = [".c", ".cpp", ".cc", ".cu"]  # required; the routing keys
symbols = true                           # optional bools (informational today)
references = true
call_graph = true
types = false

[requirements]
executables = ["clang"]                  # optional; each must be on PATH
python = ["clang-libs==1.8"]             # optional pip specs (import-checked)
```

- `extensions` is how `main` decides which files to scan and how
  `extract()` routes. It is **required** — without it the registry cannot
  route. Two backends claiming the same extension (or the same `name`)
  put both into `conflict` status: neither routes (no silent shadowing).
- `api_version` is the contract version this registry speaks
  (`SUPPORTED_API_VERSIONS` in `backends/__init__.py`). A backend that
  declares a version the registry does not support is refused with a
  clear message instead of silently emitting a shape the pipeline
  does not understand.
- The capability booleans are metadata today (visible in
  `--list-backends`); the pipeline does not gate features on them yet.
- `requirements` are checked at load time: each `executables` entry with
  `shutil.which`, each `python` spec for importability (PEP 503
  normalized: `tree-sitter` → `tree_sitter`). Unmet requirements mark the
  backend `unavailable` — other backends keep working.

### Statuses (`--list-backends`)

| status        | meaning                                          |
|---------------|--------------------------------------------------|
| `ready`       | imports cleanly, requirements met → routes       |
| `unavailable` | import failed, or an executable/package missing  |
| `invalid`     | manifest missing/invalid/unsupported api_version |
| `conflict`    | name or extension also claimed by another backend|

## extract() contract

```python
def extract(source: str, relpath: str) -> dict:
    ...
```

Returns:

```python
{
  'functions': [{
      'id': str,              # unique, e.g. 'fn:<relpath>::<name>@<line>'
      'name': str,            # last dotted part ('Vec3.normalize' → 'normalize')
      'qualified': str,       # full dotted name ('Vec3.normalize')
      'line': int,            # 1-based, line of the name/def keyword
      'end_line': int,        # 1-based, last line of the body
      'params': [str],        # parameter names in order (defaults stripped)
      'vararg': bool,         # true if the signature is variadic
      'body': str,            # the exact source lines, joined with '\n'
                               # (== source.splitlines()[line-1:end_line])
      'developer_comment': str | None,   # see comment-glue rule below
  }],
  'file_vars': [{'name': str, 'line': int, 'init': str}],
      # init is one of: 'empty' | 'table' | 'string' | 'number' |
      #                 'function' | 'call' | 'expr'
  'calls': [{'callee': str | None, 'line': int, 'method': str | None}],
      # direct callee name (possibly dotted, e.g. 'math.sqrt', 'Vec3.dot').
      # Method calls (obj:method in Lua, obj.method(...) in Python) split
      # into callee='obj', method='method'.
      # callee is None when the receiver is computed at runtime
      # (`open(..).read()`, `cfg['k'].update(..)`, `getattr(..)(..)`);
      # the method is still recorded so the reference stays VISIBLE and the
      # resolver classifies it as external (`?.method` / `?`).
      # A dotted module path (`deep.pack.mod`) is a valid callee: the
      # resolver may resolve it to a module file and then to a method in it.
  'imports': [{'module': str, 'line': int, 'bind': str | None,
               'name': str | None, 'level': int}],
      # module: the module path (Lua 'require' arg, Python 'import X' /
      #         'from X import ...'); for a Python RELATIVE import the
      #         backend already computes the effective (slash-separated)
      #         target path relative to the importing file.
      # bind:   the local name the import introduces ('as' alias, or the
      #         imported symbol when 'from X import y').
      # name:   the specific symbol inside the module (for 'from X import y'
      #         the imported y; None for a plain module import).
      # level:  relative-import depth (0 = absolute).
}
```

Invariants (the pipeline relies on these):

- **1-based line numbers.** `line` and `end_line` are 1-based and point
  into the same `source` string that was passed to `extract()`.
- **Exact body.** `body` must be exactly
  `source.splitlines()[line-1:end_line]` joined with `\n` — the render
  layer slices by these lines and will show the wrong code if they drift.
- **Document order.** Lists are in source order. The graph and render
  depend on stable, deterministic output for identical input.
- **Per file.** Backends see one file at a time. Cross-file links are
  resolved later by `graph.py` (see below). Do not open other files.
- **No exceptions for unnameable constructs.** If a construct cannot be
  named, skip it; do not raise. A raise aborts that file's analysis (caught
  and logged upstream, but the file is lost).
- **Definitions are kept, not collapsed.** A name defined more than once in
  one file (a redefinition, or a nested def sharing a name with a module
  def) yields one node per definition — the resolver picks which one each
  call site links to by *scope*: the definition visible at the call line
  wins (a nested def shadows the module level; the later of two module
  defs wins from its point onward). Do NOT dedupe redefinitions away.
- **Dedup is by identity.** The same (name, line) is never recorded twice;
  same for calls/vars on the same line.

### Optional module-level exports

- `BUILTIN_NAMES: set[str]` — names that are **not** cross-file links
  (language builtins, stdlib, self/cls). `graph.py` asks
  `backends.builtins_for(relpath)`; without it every undefined name
  becomes a dangling graph edge.
- `module_candidates(module, relpath) -> list[str]` — the relpaths a
  language import of `module` could resolve to (e.g. Python
  `import physics.vec3` → `['physics/vec3.py', 'physics/vec3/__init__.py', ...]`).
  Without it the registry falls back to
  `<module><ext>` and `<module>/init<ext>` (plus the dotted→path form).
- Comment-glue helpers live in `backends/_shared.py`:
  `_all_comments(root)`, `_dev_comment(comments, fn_line, clean)` — use
  them so `developer_comment` behaves identically across languages.

## Comment glue (developer_comment)

A comment is *glued* to a function when its **last line is exactly the
line above the function's first line** (no blank line or code between
them). The block is the **maximal run**: keep extending upward while the
previous comment's last line sits exactly on the line above the current
top. Any other content between comment and function (code, blank line)
breaks the glue → `None`.

Backends supply a per-language `clean(node)` that strips the comment
markers (Lua `comment_content`, Python leading `#` + one space).

## Adding a language

1. Create `backends/<lang>/__init__.py` with `extract(source, relpath)`
   (and optionally `BUILTIN_NAMES`, `module_candidates`).
2. Add `backends/<lang>/manifest.toml` — declare `name`, `version`,
   `api_version = "1"`, `extensions`, and its `requirements`.
3. Make its requirements available (`pip install` the python specs; the
   executables on PATH).
4. `main.py --list-backends` → status `ready`. Done — the pipeline picks
   its files up automatically.

External backends (not committed here): `main.py --install
<git-url>` clones the repo into `backends/<name>/`, pip-installs its
declared python deps, and reports the resulting status.
`main.py --remove <manifest-name>` deletes it.

> **Trust note:** installing a backend runs third-party code at import
> time and `pip install`s whatever it declares — the same trust decision
> as any dependency. Review the backend repo before `--install`.

## What must NOT change

- The `functions/file_vars/calls/imports` key names and record shapes
  above (the render + graph + LLM context layers depend on them).
- The `id` formats — `fn:<relpath>::<name>@<line>`,
  `var:<relpath>::<name>@<line>` — are the graph node keys and the LLM
  record-cache keys. A format change orphans existing cached records.
- 1-based line numbers and the exact-body invariant.

## Reference implementations

`backends/lua/__init__.py` (tree-sitter-lua) and
`backends/python/__init__.py` (tree-sitter-python) are the reference
implementations. Both use `tree-sitter` (pinned in `requirements.txt` and
re-declared in their manifests) and the `_shared.py` comment-glue helpers.
No hand-rolled tokenizers.
