# ISSUES.md — test findings from test_codebases runs

Generated while running kodama-docs against the `test_codebases/lua` and
`test_codebases/python` N-body simulation samples. Status per issue is
updated as fixes land.

## 1. CRITICAL (Lua) — colon-method function definitions are dropped entirely

**Status: OPEN (reproduced, root-caused)**

Lua `function T:m(...)` (colon / method-definition) syntax produces no
function record at all. Consequences observed in the generated docs:

- `test_codebases/lua/codebase/body.lua` (39 lines, 4 methods `Body:new`,
  `Body:reset`, `Body:apply_force`, `Body:kinetic_energy`) → **0 functions**
  extracted; the generated page summary even claims "The file contains no
  functions".
- `test_codebases/lua/codebase/nbody.lua` (87 lines, 3 methods including the
  long `NBody:accelerations`) → **0 functions** extracted. The long-function
  chunk-and-merge path is therefore never exercised by the Lua sample.
- Call-graph edges into those methods are missing (e.g. `sim:accelerations`
  in `main.lua` has no target symbol).

Dot-method definitions (`function V.add(a, b)`) extract correctly, so this is
specific to the colon form.

**Root cause (identified in `backends/lua.py`):** for `function_declaration`
nodes, the name is resolved with `_ident()`/`_dotted()`. Both only follow
`identifier` and `dot_index_expression` nodes. tree-sitter-lua parses
`function Body:new(x)` with a `method_index_expression` name node (fields
`table`, `method`), so the name resolves to `None` and the function is
silently skipped in `walk()`.

**Fix plan:** extend name resolution (and `_dotted()`) to follow
`method_index_expression` (`table` → prefix, `method` → last part), producing
e.g. `Body.new`, and prepend the implicit `self` parameter so Lua method docs
match Python's explicit `self`.

## 2. MINOR (Lua) — method calls on indexed tables not recorded

**Status: OPEN (accepted limitation for now)**

`bodies[i]:kinetic_energy()` in `nbody.lua` does not appear in the calls
list: `_callee()` only resolves call targets whose table part is a plain
identifier or dot chain. Plain identifier receivers work (`sim:step`,
`Body:new` are captured); receivers that are index/suffix expressions are
dropped. Recording them as unresolvable bare method names is possible but low
value; left as a documented limitation.

## 3. MINOR (Python) — list/set literals classified as `expr` instead of `table`

**Status: OPEN (root-caused)**

`PALETTE = ["o", "+", "*", "x"]` in `test_codebases/python/codebase/render.py`
is rendered with init `expr` in the variables table instead of `table`.

**Root cause (identified in `backends/python.py`):** `_classify()` matches
node types `dictionary`, `list_display`, `set_display`, `tuple`, but with
tree-sitter-python 0.25 the literal node types are `list` and `set`
(verified by dumping parse trees). Dictionary and tuple still map correctly.

**Fix plan:** add `list` and `set` to the `table` branch of `_classify()`.

## 4. NOTE (Python) — class methods are not qualified with the class name

**Status: OPEN (accepted design limitation)**

Python method names are recorded bare (`__init__`, `reset`, …) rather than
qualified (`Body.__init__`), unlike Lua dot-methods (`V.add`). Within a file
page this is unambiguous; across files names like `__init__` collide and the
graph's by-name index keeps only one. Impact is limited because symbol links
use per-file node ids, but the limitation is documented here for awareness.

## Verified-correct behaviour (both samples)

- All non-method functions and all file variables extracted, with correct
  names, line numbers, parameters, and init kinds (modulo issue 3).
- Developer-comment gluing works as designed: the comment block immediately
  above a definition is attached (multi-line blocks joined, rendered under
  "Developer comment"), and the negative case (comment separated by a blank
  line) is correctly *not* glued — verified in `vec3.lua` / `vec3.py`
  `normalize`.
- Chunk-and-merge path exercised by Python `NBody.accelerations` (26 lines >
  `max_function_lines: 20`): chunk records written to `data/chunks/`, merged
  doc produced, 0 failed tasks.
- External modules (`require "log"` / `import random`) produce `mod:*` graph
  nodes without fabricating file pages.
- LLM runs: Lua 31 tasks / Python 43 tasks, `failed=0` on both.
