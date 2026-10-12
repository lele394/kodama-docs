# main.py

## Summary

This is the entry-point script for a small N-body simulation demo. It defines two body-configuration generators (a circular orbital system with a central mass and a seeded random scatter), a tick function that computes total energy, updates accelerations and positions, and renders a frame, and a main function that instantiates the NBody simulator and Renderer, selects a body set based on the MODE constant, and advances the simulation for a fixed number of time steps.
**Main purpose:** To provide the executable entry point that sets up an N-body system, steps it forward in time, and produces rendered output for a configurable number of frames.
**Role in project:** Serves as the top-level driver script that wires together the NBody simulator, body constructors, and Renderer into a single runnable demonstration.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [make_circular_system](#fn-make_circular_system-16) | 16 | n | Creates a system of n+1 bodies: one central body of mass 1000 at the origin and n lighter bodies (mass 1) arranged on concentric circular or … |
| [make_random_system](#fn-make_random_system-29) | 29 | n, seed | Creates and returns a list of n randomly initialized Body objects with positions in [-10, 10], velocities in [-0.1, 0.1], a fixed zero value … |
| [tick](#fn-tick-43) | 43 | sim, bodies, renderer, dt | Advances the N-body simulation by one time step: computes total energy, updates accelerations, integrates positions/velocities, renders the  … |
| [main](#fn-main-51) | 51 |  | Initializes an N-body simulation and a renderer, populates the system with either 8 circular or 12 random bodies depending on MODE, advances … |

### make_circular_system <a id="fn-make_circular_system-16"></a>

*main.py:16-25*

**Developer comment**

> Build n bodies on a circular orbit around a central mass of 1000.

**Description**

Creates a system of n+1 bodies: one central body of mass 1000 at the origin and n lighter bodies (mass 1) arranged on concentric circular orbits with tangential velocities appropriate for circular motion.

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of orbiting bodies to create around the central body. |

**Outputs**

| Name | Description |
| --- | --- |
| `bodies` | A list of n+1 Body instances: one central body and n orbiting bodies with circular-orbit positions and tangential velocities. |

**References**

- Body

**Uncertainties**

- The exact signature and semantics of the Body constructor (7 positional arguments: likely x, y, z, vx, vy, vz, mass) is inferred from usage but not defined in this snippet.
- Whether the z-component of velocity is always zero implies a planar (2D) simulation, but this is assumed rather than stated.
- The gravitational constant used in the velocity formula v = sqrt(1000/r) is implicitly 1, which may be a project-wide convention not visible here.

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

Creates and returns a list of n randomly initialized Body objects with positions in [-10, 10], velocities in [-0.1, 0.1], a fixed zero value, and a mass/parameter of 1 + random.random(), using a seeded RNG for reproducibility.

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of Body objects to create in the system. |
| `seed` | Seed value passed to random.seed for deterministic random number generation. |

**Outputs**

| Name | Description |
| --- | --- |
| `bodies` | A list of n Body instances with randomly assigned properties. |

**Side effects**

- Seeds the global random module via random.seed(seed), affecting subsequent random number generation in the process.

**References**

- Body

**Uncertainties**

- The exact parameter names and semantic meaning of each of the 7 arguments passed to the Body constructor are not visible from this function alone.
- Whether the 6th argument (0) and 7th argument (1 + random.random()) represent mass, charge, or other physical properties is unknown without the Body class definition.

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

Advances the N-body simulation by one time step: computes total energy, updates accelerations, integrates positions/velocities, renders the frame, and returns energy, the rendered frame text, and a statistics line.

**Parameters**

| Name | Description |
| --- | --- |
| `sim` | Simulation object providing total_energy, accelerations, and step methods. |
| `bodies` | Collection of body objects representing the particles in the system. |
| `renderer` | Renderer object responsible for drawing bodies and producing a stats line. |
| `dt` | Time-step size for the integration step. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A tuple of (total_energy, joined_frame_string, stats_line). |

**Side effects**

- Mutates the bodies collection via sim.accelerations(bodies) (presumably sets acceleration attributes).
- Mutates the bodies collection via sim.step(bodies, dt) (presumably updates positions and velocities).
- Calls renderer.draw_all(bodies), which may update renderer internal display state.

**References**

- sim.total_energy
- sim.accelerations
- sim.step
- renderer.draw_all
- renderer.stats_line

**Uncertainties**

- Whether sim.accelerations and sim.step modify bodies in place or replace elements.
- What renderer.draw_all returns internally (assumed to be an iterable of strings based on the join).
- The exact format and content of renderer.stats_line output.
- The type and structure of the bodies collection (list, tuple, custom container).
- Whether sim.total_energy is computed before or after the step (it is computed before in this code, but physical intent is unclear).

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

Initializes an N-body simulation and a renderer, populates the system with either 8 circular or 12 random bodies depending on MODE, advances the simulation for RUNS ticks at a fixed timestep, and returns the total number of bodies.

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Integer count of bodies in the simulation (8 if MODE is 'circular', 12 otherwise), returned via len(bodies). |

**Side effects**

- Instantiates NBody and Renderer objects.
- Calls tick(sim, bodies, renderer, dt) RUNS times, which likely mutates simulation state, body positions/velocities, and renders frames.

**References**

- NBody
- Renderer
- [make_circular_system](main.py.md#fn-make_circular_system-16)
- [make_random_system](main.py.md#fn-make_random_system-29)
- [tick](main.py.md#fn-tick-43)
- [MODE](main.py.md#variables)
- [FPS](main.py.md#variables)
- [RUNS](main.py.md#variables)
- os.time

**Uncertainties**

- The runtime values of the module-level constants MODE, FPS, and RUNS are not visible in this snippet.
- Whether 'os.time()' refers to the standard library time module or a project-specific os module is unclear (standard os has no time() function).
- The exact state mutations performed by tick (e.g., position integration, rendering to a window) are not visible here.

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
| `FPS` | 10 | number | A numeric constant named FPS that most likely defines the target frames-per-second rate for the simulation or rendering loop in the N-body d … |
| `RUNS` | 11 | number | A module-level numeric constant in main.py, likely used to specify how many simulation runs or iterations to perform. |
| `MODE` | 12 | string | A string variable defined in main.py that holds a mode identifier, likely used to select the simulation or execution mode for the N-body dem … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
