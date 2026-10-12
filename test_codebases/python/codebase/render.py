"""render — minimal text renderer for the nbody demo."""

WIDTH = 60
HEIGHT = 24
TITLE = "nbody demo"
PALETTE = ["o", "+", "*", "x"]


class Renderer:
    """Coarse-grid renderer: projects bodies onto a 2D character frame."""

    # Draw one body as a palette marker on a coarse 2D grid.
    def draw_body(self, body):
        ix = int((body.x / 20.0 + 1.0) * (WIDTH - 1) / 2.0)
        iy = int((body.y / 20.0 + 1.0) * (HEIGHT - 1) / 2.0)
        mark = PALETTE[int(abs(body.mass) % len(PALETTE))]
        return (min(max(ix, 0), WIDTH - 1),
                min(max(iy, 0), HEIGHT - 1), mark)

    # Draw every body on a fresh frame, returning the rendered lines.
    def draw_all(self, bodies):
        grid = [[" "] * WIDTH for _ in range(HEIGHT)]
        for body in bodies:
            ix, iy, mark = self.draw_body(body)
            grid[iy][ix] = mark
        return ["".join(row) for row in grid]

    # One-line stats: body count and total energy.
    def stats_line(self, n, energy):
        return f"{TITLE}: {n} bodies, E={energy:.3e}"
