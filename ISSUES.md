# ISSUES.md — test findings from test_codebases runs

Generated while running kodama-docs against the `test_codebases/lua` and
`test_codebases/python` N-body simulation samples. Status per issue is
updated as fixes land.

## 1. CRITICAL (Lua) — colon-method function definitions are dropped entirely

**Status: FIXED (verified — see "Fixes landed")**

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

**Fix landed:** `backends/lua.py` — `_dotted()` gained an `allow_method`
mode following `method_index_expression`, and the `function_declaration` case
in `walk()` now names colon methods `Table.method` and prepends the implicit
`self` parameter. Verified: body.lua 4/4 and nbody.lua 3/3 methods extracted
(e.g. `Body.new(self, x, y, z, vx, vy, vz, mass)`,
`NBody.accelerations(self, bodies)`), including the multi-line developer
comment on `NBody:accelerations` and the chunk-and-merge path for it.

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

**Fix landed:** `backends/python.py` — `_classify()` now maps `list` and
`set` (with the legacy `list_display`/`set_display` names kept for
compatibility) to `table`. Verified: `PALETTE` renders as init `table` in
`render.py`'s variables table.

## 5. MINOR (both) — method-call edges never linked to the method

**Status: FIXED (verified — see "Fixes landed")**

Even when a method call was recorded (Lua `sim:accelerations(bodies)`,
`Body:new(...)`; Python dotted calls), the graph resolver only used the
receiver name and ignored the recorded `method` field, so every call on an
instance resolved to an `ext:` node (`ext:sim`, `ext:Body`). Methods
therefore had no "Call graph" (callers) section at all — e.g. `Body.new` and
`NBody.accelerations` showed none despite being called from `main.lua`.

**Root cause (identified in `kodama_docs/graph.py`):** `resolve_callee()`
was called with `c['callee']` only; `c['method']` was unused.

**Fix landed:** `resolve_callee(name, method)` now tries, for method calls,
(1) an exact qualified match `name.method` in the qualified-name map (covers
`Body:new` → `Body.new`), then (2) a method name that is unique across the
project (`accelerations` → `NBody.accelerations`). Ambiguous method names
fall through to the previous receiver-based resolution, keeping the
conservative "ambiguous stays unlinked" policy. Verified: `Body.new`,
`NBody.accelerations`, `NBody.step`, `NBody.total_energy` now list their
callers in `main.lua`/`nbody.lua`.

## 6. MINOR (Python) — method calls with plain-name receivers dropped

**Status: FIXED (verified — see "Fixes landed")**

In the Python sample, calls whose receiver is a plain name are dropped
entirely: `b.kinetic_energy()` in `nbody.py`, `math.sqrt(d2)`, and
`renderer.draw(...)`-style instance calls never reach the calls list (only
bare-name calls like `len`, `range`, `Vec3` are recorded). So `NBody.total_energy`
has no outgoing CALLS edge to `Body.kinetic_energy` or `Vec3.length`.

**Root cause (identified in `backends/python.py`):** `note_call()` records an
`attribute` callee only when `_dotted()` can resolve its receiver; the
receiver was read through the `value` field, but in tree-sitter-python 0.25
the `attribute` node exposes `object` (and `attribute`), so the receiver was
always `None`, the callee fell back to `expr`, and `note_call()` bailed out.

**Fix plan:** accept `name` as a base node in `_dotted()` (recording the
receiver as a bare name, e.g. callee `b` + method `kinetic_energy`), letting
graph resolution in issue 5 link unique method names.

**Fix landed:** `backends/python.py` — `note_call()` now reads the receiver
from the `object` field (`value` kept as a fallback) and `_dotted()` accepts
a plain `name`/`identifier` base. Verified: `b.kinetic_energy()`,
`sim.accelerations/step/total_energy`, `renderer.draw_all/stats_line`,
`self.draw_body`, `self.dot/length/scale` are all recorded; the generated
pages now show cross-file callers (e.g. `Body.kinetic_energy` lists
`NBody.total_energy:63` in `nbody.py`, and `Renderer.draw_body` lists
`Renderer.draw_all` in `render.py`).

## 4. NOTE (Python) — class methods are not qualified with the class name

**Status: OPEN (accepted design limitation)**

Python method names are recorded bare (`__init__`, `reset`, …) rather than
qualified (`Body.__init__`), unlike Lua dot-methods (`V.add`). Within a file
page this is unambiguous; across files names like `__init__` collide and the
graph's by-name index keeps only one. Impact is limited because symbol links
use per-file node ids, but the limitation is documented here for awareness.

## Verified-correct behaviour (both samples)

- All non-method functions and all file variables extracted, with correct
  names, line numbers, parameters, and init kinds (modulo issue 3, now fixed).
- Developer-comment gluing works as designed: the comment block immediately
  above a definition is attached (multi-line blocks joined, rendered under
  "Developer comment"), and the negative case (comment separated by a blank
  line) is correctly *not* glued — verified in `vec3.lua` / `vec3.py`
  `normalize`.
- Chunk-and-merge path exercised by Python `NBody.accelerations` (26 lines >
  `max_function_lines: 20`) **and** Lua `NBody.accelerations` once colon
  methods extract: chunk records written to `data/chunks/`, merged doc
  produced, 0 failed tasks.
- External modules (`require "log"` / `import random`) produce `mod:*` graph
  nodes without fabricating file pages.
- Cross-file method callers are linked on both samples (issue 5/6 fixes),
  including `Body.new` ← `make_circular_system`/`make_random_system` (lua)
  and `Body.kinetic_energy` ← `NBody.total_energy` (python).
- LLM runs: first pass Lua 31 tasks / Python 43 tasks, `failed=0` on both;
  fix-round re-runs Lua 38 tasks + Python (all cached), `failed=0`.
