# CLI

`main.py` is the only entry point. There is no installed console script; everything is `python main.py …`. All flags live on one flat parser (no subcommands except `test-backend`).

## All flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--config PATH` | `settings.yaml` | config file (`.yaml` or `.yml`); a relative path resolves against the config's own directory for sibling keys. |
| `--no-llm` | off | offline mode: no model calls, stub prose, no per-task delays. Fast first pass / structure check. See [Caching](../02%20-%20How%20It%20Works/08%20-%20Caching.md). |
| `--fresh` | off | ignore the per-file analysis cache (`<data_dir>/symbols.json`) and re-extract every file. Records and docs are still reused. |
| `--purge` | off | delete the output dir, data dir, and record caches and **exit** — no run happens. |
| `--regenerate` | off | same deletes as `--purge`, **then run** from scratch. (The two are mutually exclusive by construction — one runs, one doesn't.) |
| `--list-backends` | — | print the backend registry (name, version, api, extension, status, issues) and exit. |
| `--install URL` | — | git-clone a backend repo into `backends/<name>/` and pip-install its declared python deps; exit. |
| `--remove NAME` | — | delete one installed backend; exit. |
| `--serve` | off | start the [web server](05%20-%20Web%20Server.md) on `web/web_settings.yaml` (default `http://127.0.0.1:8123`) and exit. |
| `test-backend --backend NAME` | — | run the named backend's self-test harness and exit; `--backend` is required. |

## Precedence

The CLI is evaluated in this order; the first matching mode wins and exits:

1. **`--list-backends` / `--install` / `--remove`** — printed, executed, done.
2. **`test-backend`** — runs the harness with the named backend (status must be `ready`); exit code 0 on a full pass, non-zero on any failed check.
3. **`--purge`** / **`--regenerate`** — delete `output_dir`, `data_dir`, and the record caches (`--regenerate` continues, `--purge` stops).
4. **`--serve`** — web server on the config's output dir (or `docs_dir`).
5. **the pipeline run** — scan → analyze → graph → [LLM phase](../02%20-%20How%20It%20Works/05%20-%20LLM%20Phase.md) → [render](../02%20-%20How%20It%20Works/07%20-%20Rendering.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success (including `--no-llm` runs, purges, clean backend lists). |
| `1` | at least one LLM task failed after retries — docs were still written for everything that succeeded; the failing prose is a visible placeholder, not silent. |
| non-zero | errors (`SystemExit` messages: config not found, no ready backend for a language, `test-backend` without `--backend`, self-test failures). |

## Typical invocations

```bash
# inspect the project, no model
python main.py --no-llm

# full run (uses .env + settings.yaml)
python main.py

# full run from a clean slate (drops docs, records, caches)
python main.py --regenerate

# serve the last run
python main.py --serve

# what backends are here, and what is missing?
python main.py --list-backends

# verify the Python backend (CI-friendly)
python main.py test-backend --backend python
```

Related: [First Run](../01%20-%20Getting%20Started/02%20-%20First%20Run.md), [Config Reference](../04%20-%20Reference/01%20-%20Config%20Reference.md), [Troubleshooting](../06%20-%20Troubleshooting/01%20-%20LLM%20Problems.md).
