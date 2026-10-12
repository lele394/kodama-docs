# render.py

## Summary

This module provides terminal-based rendering for an N-body simulation. It maps body coordinates to a fixed-width text grid using a linear coordinate transformation and assigns character marks based on body mass via a palette. It also formats a status line containing the simulation title, body count, and total energy.
**Main purpose:** To render N-body simulation state as a text-grid display and a summary status line for terminal output.
**Role in project:** Serves as the display/output layer of the N-body simulation demo, converting internal simulation state into human-readable terminal graphics.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [draw_body](#fn-draw_body-13) | 13 | self, body | Converts a body's world coordinates into clamped pixel coordinates for rendering and selects a palette mark based on the body's mass. Return … |
| [draw_all](#fn-draw_all-21) | 21 | self, bodies | Renders all simulation bodies onto a character grid of fixed dimensions and returns the grid as a list of strings, one per row. |
| [stats_line](#fn-stats_line-29) | 29 | self, n, energy | Formats and returns a human-readable status string containing the simulation title, the number of bodies, and the total energy in scientific … |

### draw_body <a id="fn-draw_body-13"></a>

*render.py:13-18*

**Developer comment**

> Draw one body as a palette marker on a coarse 2D grid.

**Description**

Converts a body's world coordinates into clamped pixel coordinates for rendering and selects a palette mark based on the body's mass. Returns a tuple of (x_pixel, y_pixel, mark).

**Parameters**

| Name | Description |
| --- | --- |
| `self` | Instance of the containing render class. |
| `body` | A body object with x, y, and mass attributes to be rendered. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A 3-element tuple: (clamped_x_pixel, clamped_y_pixel, mark) where coordinates are clamped to [0, WIDTH-1] / [0, HEIGHT-1] and mark is a palette entry chosen by abs(body.mass) % len(PALETTE). |

**References**

- [WIDTH](render.py.md#variables)
- [HEIGHT](render.py.md#variables)
- [PALETTE](render.py.md#variables)

**Uncertainties**

- The exact types of WIDTH, HEIGHT, and PALETTE are not visible (presumably module-level constants or class attributes).
- The structure of the body object (e.g., whether x, y, mass are simple attributes or properties) is not defined in this snippet.

```py
def draw_body(self, body):
        ix = int((body.x / 20.0 + 1.0) * (WIDTH - 1) / 2.0)
        iy = int((body.y / 20.0 + 1.0) * (HEIGHT - 1) / 2.0)
        mark = PALETTE[int(abs(body.mass) % len(PALETTE))]
        return (min(max(ix, 0), WIDTH - 1),
                min(max(iy, 0), HEIGHT - 1), mark)
```

**Call graph**

- [render.py](render.py.md)
  - [draw_all:24](render.py.md#fn-draw_all-21)

---

### draw_all <a id="fn-draw_all-21"></a>

*render.py:21-26*

**Developer comment**

> Draw every body on a fresh frame, returning the rendered lines.

**Description**

Renders all simulation bodies onto a character grid of fixed dimensions and returns the grid as a list of strings, one per row.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | Instance of the renderer class that provides the draw_body method. |
| `bodies` | Iterable of body objects to be rendered; each is passed to self.draw_body. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A list of strings, each representing one row of the rendered grid (HEIGHT strings, each WIDTH characters long). |

**References**

- [WIDTH](render.py.md#variables)
- [HEIGHT](render.py.md#variables)
- [draw_body](render.py.md#fn-draw_body-13)

**Uncertainties**

- The exact values or definitions of WIDTH and HEIGHT (presumably module-level constants in render.py).
- What self.draw_body returns for ix, iy, mark and whether it mutates the body object.

```py
def draw_all(self, bodies):
        grid = [[" "] * WIDTH for _ in range(HEIGHT)]
        for body in bodies:
            ix, iy, mark = self.draw_body(body)
            grid[iy][ix] = mark
        return ["".join(row) for row in grid]
```

**Call graph**

- [main.py](main.py.md)
  - [tick:47](main.py.md#fn-tick-43)

---

### stats_line <a id="fn-stats_line-29"></a>

*render.py:29-30*

**Developer comment**

> One-line stats: body count and total energy.

**Description**

Formats and returns a human-readable status string containing the simulation title, the number of bodies, and the total energy in scientific notation.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | Instance of the render class calling this method. |
| `n` | Number of bodies in the simulation. |
| `energy` | Total energy value to be formatted in scientific notation. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A formatted string like '<TITLE>: <n> bodies, E=<energy in 3-dig sci-notation>'. |

**References**

- [TITLE](render.py.md#variables)

```py
def stats_line(self, n, energy):
        return f"{TITLE}: {n} bodies, E={energy:.3e}"
```

**Call graph**

- [main.py](main.py.md)
  - [tick:48](main.py.md#fn-tick-43)

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `WIDTH` | 3 | number | Numeric constant in render.py that defines the width dimension (likely of the rendering canvas or display window) for the N-body simulation  … |
| `HEIGHT` | 4 | number | Numeric value defining the vertical dimension (height) of the render area used in the N-body simulation visualization. |
| `TITLE` | 5 | string | A string constant holding the title displayed for the simulation's rendering window or frame in the N-body demo project. |
| `PALETTE` | 6 | table | A color palette (tabular collection of colors) defined in render.py, likely used to map simulation states or bodies to visual colors during  … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
