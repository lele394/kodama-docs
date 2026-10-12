# render.py

## Summary

render.py provides a lightweight text-based renderer for an N-body simulation. It maps body positions and masses onto a fixed-size character grid (WIDTH x HEIGHT) using a color palette of symbols, and formats a title/stats line showing body count and total energy. The module exposes three methods: draw_body for a single body's grid cell and mark, draw_all to composite all bodies into a frame of strings, and stats_line for the header display.
**Main purpose:** To convert N-body simulation state into a simple ASCII grid frame and a formatted stats line for terminal display.
**Role in project:** Serves as the rendering/display layer in the small N-body simulation demo, translating numeric simulation data into a character-grid output without performing any physics computation.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [draw_body](#fn-draw_body-13) | 13 | self, body | Converts a simulation body's world coordinates into screen-pixel coordinates and selects a display mark from PALETTE based on the body's mas … |
| [draw_all](#fn-draw_all-21) | 21 | self, bodies | Renders a list of bodies onto a fixed-size text grid and returns the grid as a list of row strings. Each body's character mark is placed at  … |
| [stats_line](#fn-stats_line-29) | 29 | self, n, energy | Returns a formatted status line string displaying the simulation title, the number of bodies, and the total energy in scientific notation wi … |

### draw_body <a id="fn-draw_body-13"></a>

*render.py:13-18*

**Developer comment**

> Draw one body as a palette marker on a coarse 2D grid.

**Description**

Converts a simulation body's world coordinates into screen-pixel coordinates and selects a display mark from PALETTE based on the body's mass. Returns a tuple of (clamped_x, clamped_y, mark).

**Parameters**

| Name | Description |
| --- | --- |
| `self` | Instance of the render class (implicit). |
| `body` | A body object providing .x, .y (world coordinates) and .mass attributes. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A 3-tuple: (clamped_ix, clamped_iy, mark), where ix/iy are integer pixel coordinates clamped to [0, WIDTH-1]/[0, HEIGHT-1] and mark is an entry from PALETTE selected by body.mass. |

**References**

- [WIDTH](render.py.md#variables)
- [HEIGHT](render.py.md#variables)
- [PALETTE](render.py.md#variables)

**Uncertainties**

- The type and structure of PALETTE entries (e.g., RGB tuple, string, drawing primitive) is not visible in this function.
- The exact coordinate system convention (e.g., whether origin is top-left) is not stated here.

```py
def draw_body(self, body):
        ix = int((body.x / 20.0 + 1.0) * (WIDTH - 1) / 2.0)
        iy = int((body.y / 20.0 + 1.0) * (HEIGHT - 1) / 2.0)
        mark = PALETTE[int(abs(body.mass) % len(PALETTE))]
        return (min(max(ix, 0), WIDTH - 1),
                min(max(iy, 0), HEIGHT - 1), mark)
```

---

### draw_all <a id="fn-draw_all-21"></a>

*render.py:21-26*

**Developer comment**

> Draw every body on a fresh frame, returning the rendered lines.

**Description**

Renders a list of bodies onto a fixed-size text grid and returns the grid as a list of row strings. Each body's character mark is placed at the coordinates returned by draw_body.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The renderer instance that provides draw_body. |
| `bodies` | Iterable of body objects to be rendered onto the grid. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A list of strings, one per grid row, representing the rendered scene. |

**References**

- [WIDTH](render.py.md#variables)
- [HEIGHT](render.py.md#variables)
- self.draw_body

**Uncertainties**

- The values and origin of WIDTH and HEIGHT (likely module-level constants in render.py).
- The exact return signature of draw_body (inferred as a 3-tuple of int, int, str).
- Whether ix or iy can fall outside grid bounds, which would raise an IndexError.
- The concrete type of elements in the bodies iterable (likely a Body class from another module).

```py
def draw_all(self, bodies):
        grid = [[" "] * WIDTH for _ in range(HEIGHT)]
        for body in bodies:
            ix, iy, mark = self.draw_body(body)
            grid[iy][ix] = mark
        return ["".join(row) for row in grid]
```

---

### stats_line <a id="fn-stats_line-29"></a>

*render.py:29-30*

**Developer comment**

> One-line stats: body count and total energy.

**Description**

Returns a formatted status line string displaying the simulation title, the number of bodies, and the total energy in scientific notation with three decimal places.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The renderer instance owning this method. |
| `n` | Number of bodies in the simulation. |
| `energy` | Total energy of the simulation. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A formatted string in the form '<TITLE>: <n> bodies, E=<energy:.3e>'. |

**References**

- [TITLE](render.py.md#variables)

**Uncertainties**

- The exact value of the TITLE constant used in the format string.

```py
def stats_line(self, n, energy):
        return f"{TITLE}: {n} bodies, E={energy:.3e}"
```

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `WIDTH` | 3 | number | A numeric constant defining the pixel width of the rendering area used by the N-body simulation visualization in render.py. |
| `HEIGHT` | 4 | number | A numeric constant defining the height (in pixels) of the rendering surface used to draw the N-body simulation. It is referenced within the  … |
| `TITLE` | 5 | string | A string constant defined in render.py that holds a title, most likely used as the display or window title for the simulation's rendering su … |
| `PALETTE` | 6 | expr | A color palette definition in render.py, likely holding a sequence of color values used when drawing the N-body simulation objects. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
