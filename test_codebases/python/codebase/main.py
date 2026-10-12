"""main — entry point: builds a body system and runs a fixed number of steps."""

import math
import os

from body import Body
from nbody import NBody
from render import Renderer

FPS = 60
RUNS = 300
MODE = "circular"


# Build n bodies on a circular orbit around a central mass of 1000.
def make_circular_system(n):
    bodies = [Body(0, 0, 0, 0, 0, 0, 1000)]
    for i in range(1, n + 1):
        r = 10 + i * 2
        v = (1000 / r) ** 0.5
        a = 2 * math.pi * i / n
        bodies.append(Body(
            math.cos(a) * r, math.sin(a) * r, 0,
            -math.sin(a) * v, math.cos(a) * v, 0, 1))
    return bodies


# Build n bodies at pseudo-random positions with small random velocities.
def make_random_system(n, seed):
    import random
    random.seed(seed)
    bodies = []
    for _ in range(n):
        bodies.append(Body(
            random.uniform(-10, 10), random.uniform(-10, 10),
            random.uniform(-10, 10),
            random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), 0,
            1 + random.random()))
    return bodies


# Advance one frame: compute total energy, integrate, then render.
def tick(sim, bodies, renderer, dt):
    e = sim.total_energy(bodies)
    sim.accelerations(bodies)
    sim.step(bodies, dt)
    frame = renderer.draw_all(bodies)
    return e, "\n".join(frame), renderer.stats_line(len(bodies), e)


def main():
    sim = NBody()
    renderer = Renderer()
    if MODE == "circular":
        bodies = make_circular_system(8)
    else:
        bodies = make_random_system(12, os.time())

    dt = 1 / FPS
    for _ in range(RUNS):
        tick(sim, bodies, renderer, dt)

    return len(bodies)


if __name__ == "__main__":
    main()
