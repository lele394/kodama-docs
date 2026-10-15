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
pip install -r requirements.txt
```

There is no installable package (no `pyproject.toml`/`setup.py`) — the code is run directly from the checkout, so `pip install -r requirements.txt` is the whole install. It pulls: `tree-sitter`, `tree-sitter-lua`, `tree-sitter-python`, `ruamel.yaml`, `networkx`, and `rich`.

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

A healthy install lists the built-in `kodama-lua` and `kodama-python` backends, each `ready`, with routing for `.lua` and `.py`. The Python backend also ships an end-to-end self-test (it runs a small fixture through the real graph builder and checks every call/import edge):

```bash
python main.py test-backend --backend python
```

The Lua backend does not implement the self-test protocol yet; its behavior is covered by the same generic machinery in `kodama_docs/testing.py`.

Next: [First Run](02%20-%20First%20Run.md).
