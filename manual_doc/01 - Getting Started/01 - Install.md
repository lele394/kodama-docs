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
```

`pip install -e .` installs the package in editable mode and pulls the runtime dependencies: `tree-sitter`, `tree-sitter-lua`, `tree-sitter-python`, `ruamel.yaml`, `networkx`, and `rich`.

## Set up the LLM (optional)

The LLM is read from a `.env` file in the project root (or next to your config). This is only needed for full runs, not for `--no-llm`:

```dotenv
LLM_BASE_URL=https://your-llm.example/v1
LLM_API_KEY=sk-...
LLM_MODEL=your-model-name
```

If your `settings.yaml` sets `llm.base_url: env` and `llm.api_key: env` (the defaults), these `.env` values are used. See [Configuration](03%20-%20Configuration.md).

## Verify the install

```bash
python main.py --list-backends
```

A healthy install lists the built-in `lua` and `python` backends. To check one backend's parser works end to end, run its self-test:

```bash
python main.py test-backend --backend lua
```

Next: [First Run](02%20-%20First%20Run.md).
