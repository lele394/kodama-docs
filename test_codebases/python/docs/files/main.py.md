# main.py

## Summary

This is the entry-point module for a small N-body simulation demo. It defines two system-construction helpers (a circular orbital system and a random system), a single-step tick function that computes energy, accelerations, integration, and rendering, and a main() that wires an NBody simulator and Renderer together and runs the simulation for a fixed number of frames. File-level constants FPS, RUNS, and MODE control the simulation speed, duration, and initial condition mode.
**Main purpose:** Provide the top-level driver that constructs an N-body system, steps the simulation, and renders frames for a short demo run.
**Role in project:** Serves as the project's main entry point, orchestrating the NBody simulator, Renderer, and body-system generators imported from sibling modules.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [make_circular_system](#fn-make_circular_system-16) | 16 | n | Creates a system of n+1 bodies for an N-body simulation: one central mass of 1000 at the origin and n smaller bodies (mass 1) arranged in a  … |
| [make_random_system](#fn-make_random_system-29) | 29 | n, seed | Creates and returns a list of n randomly configured Body instances, using a seeded random number generator to determine their parameters (po … |
| [tick](#fn-tick-43) | 43 | sim, bodies, renderer, dt | Executes one simulation tick: computes total energy, updates accelerations, advances all bodies by dt, renders the resulting frame, and retu … |
| [main](#fn-main-51) | 51 |  | Initializes an N-body simulation with either a circular or random body system, runs a fixed number of simulation ticks, and returns the numb … |

### make_circular_system <a id="fn-make_circular_system-16"></a>

*main.py:16-25*

**Developer comment**

> Build n bodies on a circular orbit around a central mass of 1000.

**Description**

Creates a system of n+1 bodies for an N-body simulation: one central mass of 1000 at the origin and n smaller bodies (mass 1) arranged in a circular orbit with per-body radii and tangential velocities derived from a circular-orbit approximation.

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of orbiting bodies to create (excluding the central mass). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A list of n+1 Body objects: one central body at the origin with mass 1000, followed by n bodies placed at radius 10+i*2 with tangential velocity sqrt(1000/r) and mass 1. |

**References**

- Body
- math

**Uncertainties**

- The exact meaning and order of Body constructor parameters (assumed x, y, z, vx, vy, vz, mass based on argument count).
- Whether the central body is intended to be fixed or also participates in N-body gravitational forces.

```py
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
```

**Call graph**

- [main.py](main.py.md)
  - [main:55](main.py.md#fn-main-51)

---

### make_random_system <a id="fn-make_random_system-29"></a>

*main.py:29-39*

**Developer comment**

> Build n bodies at pseudo-random positions with small random velocities.

**Description**

Creates and returns a list of n randomly configured Body instances, using a seeded random number generator to determine their parameters (positions, velocities, and a final numeric attribute).

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of Body objects to generate. |
| `seed` | Integer seed value passed to random.seed() to make the generated system reproducible. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A list of n Body objects with random positions (uniform in [-10, 10]), small random velocities (uniform in [-0.1, 0.1]), a zero value, and a value in the range [1, 2). |

**Side effects**

- Sets the global random module seed via random.seed(seed).
- Instantiates n new Body objects.

**References**

- random
- Body

**Uncertainties**

- The exact semantic meaning of each of the 7 positional arguments passed to the Body constructor (e.g., which are position, velocity, mass, or other properties).
- Whether the local `import random` shadows or reuses a module-level import of the random module.

```py
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
```

**Call graph**

- [main.py](main.py.md)
  - [main:57](main.py.md#fn-main-51)

---

### tick <a id="fn-tick-43"></a>

*main.py:43-48*

**Developer comment**

> Advance one frame: compute total energy, integrate, then render.

**Description**

Executes one simulation tick: computes total energy, updates accelerations, advances all bodies by dt, renders the resulting frame, and returns the energy, rendered frame text, and a stats line.

**Parameters**

| Name | Description |
| --- | --- |
| `sim` | Simulation object providing total_energy, accelerations, and step methods. |
| `bodies` | List of body objects to be simulated in this tick. |
| `renderer` | Renderer object providing draw_all and stats_line methods. |
| `dt` | Time step (in seconds or simulation units) to advance the simulation. |

**Outputs**

| Name | Description |
| --- | --- |
| `e` | Total energy of the system computed before the step. |
| `return value` | A string formed by joining the renderer's frame output with newline characters. |
| `return value` | A stats line string generated by renderer.stats_line with body count and energy. |

**Side effects**

- Mutates the bodies list via sim.accelerations(bodies) (likely in-place velocity/position updates).
- Mutates the bodies list via sim.step(bodies, dt) (advances positions/velocities).
- Invokes renderer.draw_all(bodies), which may produce rendering side effects.

**References**

- [total_energy](nbody.py.md#fn-total_energy-62)
- [accelerations](nbody.py.md#fn-accelerations-22)
- [step](nbody.py.md#fn-step-50)
- [draw_all](render.py.md#fn-draw_all-21)
- [stats_line](render.py.md#fn-stats_line-29)

**Uncertainties**

- Whether sim.accelerations and sim.step modify bodies in-place or rely on internal state; return values are not captured.
- The exact type/structure of the object returned by renderer.draw_all (assumed an iterable of strings based on '\n'.join usage).
- Whether renderer.stats_line returns a plain string or some other text type.

```py
def tick(sim, bodies, renderer, dt):
    e = sim.total_energy(bodies)
    sim.accelerations(bodies)
    sim.step(bodies, dt)
    frame = renderer.draw_all(bodies)
    return e, "\n".join(frame), renderer.stats_line(len(bodies), e)
```

**Call graph**

- [main.py](main.py.md)
  - [main:61](main.py.md#fn-main-51)

---

### main <a id="fn-main-51"></a>

*main.py:51-63*

**Description**

Initializes an N-body simulation with either a circular or random body system, runs a fixed number of simulation ticks, and returns the number of bodies in the system.

**Outputs**

| Name | Description |
| --- | --- |
| `return` | The number of bodies in the system (8 for circular mode, 12 for random mode), via len(bodies). |

**Side effects**

- Mutates the bodies list over RUNS iterations through repeated calls to tick (presumably updating positions, velocities, or internal NBody state).
- Creates and uses Renderer and NBody instances whose internal state may be modified by tick.

**References**

- NBody
- Renderer
- [MODE](main.py.md#variables)
- [make_circular_system](main.py.md#fn-make_circular_system-16)
- [make_random_system](main.py.md#fn-make_random_system-29)
- os
- [FPS](main.py.md#variables)
- [RUNS](main.py.md#variables)
- [tick](main.py.md#fn-tick-43)

**Uncertainties**

- The exact runtime value of MODE, FPS, and RUNS (likely module-level constants not visible in this snippet).
- The specific mutations tick performs on NBody, bodies, and Renderer (e.g., position integration, force calculation, rendering).
- Whether NBody or Renderer hold persistent state that accumulates across tick calls.

```py
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
```

**Call graph**

- [main.py](main.py.md)
  - [top-level:67](main.py.md)

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `FPS` | 10 | number | A numeric constant representing the target frames per second (FPS) for the N-body simulation's render or update loop. |
| `RUNS` | 11 | number | A module-level numeric constant in main.py that specifies the number of simulation runs to perform in the N-body demo. Typically read by the … |
| `MODE` | 12 | string | String variable that holds the current operational mode of the N-body simulation (e.g., running, paused, or setup), used to gate which behav … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
