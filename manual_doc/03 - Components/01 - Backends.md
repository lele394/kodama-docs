# Backends

A **backend** is a pluggable package that knows one language: it takes source text and returns the neutral record described in [Extraction](../02%20-%20How%20It%20Works/03%20-%20Extraction.md). Everything downstream — graph, LLM phase, rendering — is language-agnostic and only ever sees that record.

## What a backend is

A backend is a directory under `backends/` containing:

- `manifest.toml` — identity (`backend.name`, `version`, `api_version`), declared `capabilities.languages` / `capabilities.extensions`, and `requirements` (executable files and/or pip packages);
- `__init__.py` — the Python package, which **must** expose `extract(source, relpath) -> dict`;
- optional `BUILTIN_NAMES` — names the resolver should treat as language/stdlib (so calls to them never dangle as unresolved project references);
- optional `module_candidates(module, relpath)` — the file paths a language import could map to (the generic fallback guesses `x.lua`, `x/init.lua`, …; Python overrides this for `__init__.py` packages).

The full contract, including every invariant the pipeline relies on, is in `backends/backend_design.md` in the repository.

## The registry and its statuses

`backends/__init__.py` scans `backends/*/manifest.toml` on every query (no cache — installing a backend changes the directory) and reports each one with a status:

| Status | Meaning |
| --- | --- |
| `ready` | manifest valid, package imports, `extract` present, all declared requirements importable — this backend claims its extensions. |
| `unavailable` | something is missing (dependency, executable) or the import failed. |
| `conflict` | another ready backend claims the same name or the same extension. |
| `invalid` | the manifest is missing or malformed. |

Two rules make conflicts impossible in practice: **no two backends may share a name, and no two may claim the same extension** — ambiguity is a conflict for both, never a silent shadow. A file is routed to the *ready* backend that claims its extension (`EXTRACTORS`); a file with no ready backend is skipped and reported, never fatal.

`--list-backends` prints the whole table, and the registry is also what `test-backend`, `--install`, and `--remove` work against.

## Installing and removing

```bash
python main.py --install <git-url-or-path>   # clone into backends/<name>/, pip-install missing deps
python main.py --remove <name>               # delete one installed backend
```

Install runs `git clone --depth 1` with the directory name derived from the URL (lowercased, sanitized to a valid package name), then checks the manifest and pip-installs the backend's declared python requirements. **This executes third-party code at import time — only install backends you have reviewed.** A backend is live the moment its directory exists, its manifest is valid, and its requirements are met; there is no separate registration step.

## Verifying a backend

`python main.py test-backend --backend <name>` runs the backend's **self-test protocol** (implemented by the Python backend; see [Python Backend](03%20-%20Python%20Backend.md)):

1. the backend's `collect_truth()` runs a bundled fixture with the real language runtime and records every call site and import binding it resolved;
2. the fixture's `# expect: ...` marker lines pin the deliberately unresolvable cases (ambiguous names, external calls, unresolved imports) that the runtime cannot reach;
3. the harness extracts the fixture with the backend's own `extract`, builds the kodama-docs graph, and checks the graph against both sources of truth.

The graph is the artifact under test: a failure means the *translation* (code → record → graph) is wrong, and the exit code is non-zero so the harness is CI-friendly. See [Adding a Language](../08%20-%20Contributing/01%20-%20Adding%20a%20Language.md).

## The stable API

The registry exposes a small, stable surface the pipeline uses:

| Name | Used for |
| --- | --- |
| `extract(source, relpath)` | the record, per file (the contract). |
| `builtins_for(relpath)` | the backend's `BUILTIN_NAMES`, for the resolver. |
| `module_candidates(module, relpath)` | import → file resolution candidates. |
| `list_backends()` | status table for `--list-backends`. |
| `active_backend_ids()` | `name@version` per extension — stamped into `symbols.json` so a backend upgrade invalidates the analysis cache (see [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md)). |
| `install_backend(url)` / `remove_backend(name)` | backend management. |

The concrete backends ship in this repository: [Lua](02%20-%20Lua%20Backend.md) and [Python](03%20-%20Python%20Backend.md).
