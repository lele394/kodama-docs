# Install

kodama-docs is a Python package. You only need Python, `git`, and the runtime dependencies in `requirements.txt`.

## Prerequisites

- **Python 3.14** (3.11+ is expected to work).
- **git** — for installing and updating language backends.
- (Optional) an **OpenAI-compatible LLM** plus its key. You can skip this entirely and use `--no-llm` to produce the full deterministic structure with placeholder prose.

## Create a virtual environment

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e .
# or, without installing the package:
pip install -r requirements.txt
```

V0.1 is installed from the checkout. `pip install -e .` uses `pyproject.toml`
and also installs the `kodama-docs` console script; `requirements.txt` is the
dependency-only path. Either way the source tree keeps `prompts/`,
`settings.yaml`, `web/` and `icon/` next to `main.py`, which is what the
default config expects.

The runtime dependencies are `tree-sitter`, `tree-sitter-lua`,
`tree-sitter-python`, `tree-sitter-cpp`, `tree-sitter-cuda`, `ruamel.yaml`,
`networkx`, and `rich`.

## Set up the LLM (optional)

The LLM endpoint is read from a `.env` file, looked up at the project root (next to `main.py`) first, then next to your config file. This is only needed for full runs, not for `--no-llm`:

```dotenv
base_url=https://your-llm.example/v1
api_key=sk-...
```

That is all the `.env` carries. The model name is **not** a `.env` key — it comes from `llm.model` in `settings.yaml`. If your `settings.yaml` sets `llm.base_url: env` and `llm.api_key: env` (the defaults), these `.env` values are used. See [Configuration](03%20-%20Configuration.md).

## Verify the install

```bash
python main.py --list-backends
```

A healthy install lists the built-in `kodama-lua`, `kodama-python` and
`kodama-cpp` backends, each `ready`, with routing for `.lua`, `.py`, and the
C/C++/CUDA extensions. The Python backend also ships an end-to-end self-test
(it runs a small fixture through the real graph builder and checks every
call/import edge):

```bash
python main.py test-backend --backend python
```

The Lua backend does not implement the self-test protocol yet; its behavior is covered by the same generic machinery in `kodama_docs/testing.py`.

Next: [First Run](02%20-%20First%20Run.md).
