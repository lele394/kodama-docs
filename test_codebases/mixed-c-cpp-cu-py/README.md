# mixed-c-cpp-cu-py

A deliberately small, **parse-only** fixture for the `kodama-cpp` backend and
the language-aware parts of the pipeline. Nothing here needs to compile or
run: the checks are about extraction, includes, calls and rendering.

## Layers

```text
python/mixed_py/*.py        ctypes + pybind11 facade
        |                        |
        | import mixed_native    | ctypes.CDLL
        v                        v
cpp/bindings.cpp  ----------> cpp/engine.cpp ----> cpp/math.hpp
        |                        |      |
        | pybind11               |      | launch_saxpy()
        v                        v      v
   cpp/engine.hpp  ----------> c/c core.c      cuda/kernels.cu
        |                        |                 |
        +--- #include ------------+                 +--- saxpy_kernel<<<...>>>
                                                       cudaDeviceSynchronize()
```

What the fixture exercises:

- **C/C++/CUDA routing** in one scan (`.c`, `.h`, `.hpp`, `.cpp`, `.cu`,
  `.cuh`, `.py`).
- **Quoted includes** resolving to real project files, including a subdir
  (`../c/core.h`) and a public include dir (`../include/mixed/version.h`).
- **C functions** (`c_add`, `c_scale`, `mixed_version`,
  `mixed_call_count`), a global counter, and object/function-like macros.
- **C++ classes/methods**, out-of-class definitions (`Engine::step`), a
  constructor/destructor, a header-only template (`clamp_value`), and
  namespace-qualified names (`mixed.Engine.step`).
- **CUDA kernels** (`saxpy_kernel<<<...>>>`), a `__device__` function, the
  `cudaDeviceSynchronize` builtin, and `.cuh` include resolution.
- **Python**, including a relative import (`from .bridge import ...`), a
  `try: import mixed_native`, and ctypes attribute calls.
- **pybind11 bridge**: the `PYBIND11_MODULE` block is parsed into explicit
  `bindings` records. The graph gets `EXPORTS` edges from `bindings.cpp` to
  the C++ class/methods and a `BRIDGES` edge from the Python `Engine` facade
  to the C++ `mixed.Engine` class. `mixed_native.Engine(...)` calls resolve
  exactly; ctypes calls stay `inferred`, and no FFI edge is guessed.
- **C/C++/CUDA calls** are resolved where the graph can see a single project
  symbol (`Engine::step` → `c_add`/`c_scale`, `run_gpu` → `launch_saxpy`,
  `py_add` → `c_add`).
- **Multiline developer comments**: `c_add` has a two-line block comment and
  `CNative` has a two-line `#` comment; both must appear as developer
  comments.
- **LLM skip override**: `Engine::legacy_entry` and the `LegacyMath` class
  carry `kodama-docs-llm:skip`. No LLM record is generated for them, the
  class skip also covers `legacy_add`, and their pages show the skip note.

## Run

```bash
# from the repository root
.venv/bin/python main.py --config test_codebases/mixed-c-cpp-cu-py/settings.yaml --no-llm
.venv/bin/python test_codebases/mixed-c-cpp-cu-py/check_mixed.py
```

Then optionally:

```bash
.venv/bin/python main.py --config test_codebases/mixed-c-cpp-cu-py/settings.yaml --serve
```

`--no-llm` is enough for all structural checks; it writes stub prose and keeps
the deterministic symbol/graph/output pipeline intact.

## Known limits

- The shared prompts in `prompts/` still describe Lua; prose from a real LLM
  run will be generic. Extraction and graph checks do not depend on it.
- pybind11 exports are statically extracted; ctypes comments call names but
  do not declare types, so `self._lib.c_add` stays an inferred/external
  reference. Cython/torch-extension boundaries would need their own binding
  records.
- Header prototypes are intentionally not documented; only definitions are.
  Header-only inline/template definitions are.
