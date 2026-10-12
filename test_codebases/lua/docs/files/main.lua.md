# main.lua

## Summary

This is the main entry-point script for an N-body simulation demo written in Lua. It provides two system generators—make_circular_system (n bodies in circular orbits around a central mass of 1000) and make_random_system (n bodies with seeded random positions and velocities)—and a tick function that logs total energy, computes accelerations, and integrates bodies forward by one timestep. The main function selects a mode, initializes the body list, and runs a fixed number of simulation steps.
**Main purpose:** To set up an N-body system (circular or random) and execute a configurable number of simulation timesteps while logging total energy at each step.
**Role in project:** As main.lua, it is the top-level script that orchestrates the N-body simulation by wiring together the Body, NBody, and log modules for a demo run.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [make_circular_system](#fn-make_circular_system-12) | 12 | n | Creates a table of Body objects representing a central body (mass 1000 at the origin) plus n smaller bodies (mass 1) arranged in circular or … |
| [make_random_system](#fn-make_random_system-26) | 26 | n, seed | Creates a table of n randomly generated Body objects with positions in [-10,10], small in-plane velocities in [-0.1,0.1], zero z-velocity, a … |
| [tick](#fn-tick-39) | 39 | sim, bodies, dt | Performs one tick of the N-body simulation by recording the current total energy, computing accelerations, advancing the bodies by the time  … |
| [main](#fn-main-46) | 46 |  | Initializes an N-body system (circular or random) based on the MODE setting, advances the simulation for RUNS timesteps using tick, and retu … |

### make_circular_system <a id="fn-make_circular_system-12"></a>

*main.lua:12-23*

**Developer comment**

> Build n bodies on a circular orbit around a central mass of 1000.

**Description**

Creates a table of Body objects representing a central body (mass 1000 at the origin) plus n smaller bodies (mass 1) arranged in circular orbits with evenly spaced angles and tangential velocities consistent with a circular orbital speed of sqrt(1000/r).

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of orbiting bodies to create in addition to the central body. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A Lua table containing 1 + n Body instances: the first is the central body at the origin, the rest are orbiting bodies with computed positions and tangential velocities. |

**References**

- [Body](body.lua.md)

**Uncertainties**

- The exact constructor signature of Body:new is inferred from positional arguments (x, y, z, vx, vy, vz, mass) but not explicitly documented in this snippet.
- The gravitational constant G is implicitly 1 based on v = sqrt(1000/r); it is not referenced as a named symbol in the code.

```lua
local function make_circular_system(n)
  local bodies = { Body:new(0, 0, 0, 0, 0, 0, 1000) }
  for i = 1, n do
    local r = 10 + i * 2
    local v = math.sqrt(1000 / r)
    local a = 2 * math.pi * i / n
    table.insert(bodies, Body:new(
      math.cos(a) * r, math.sin(a) * r, 0,
      -math.sin(a) * v, math.cos(a) * v, 0, 1))
  end
  return bodies
end
```

**Call graph**

- [main.lua](main.lua.md)
  - [main:49](main.lua.md#fn-main-46)

---

### make_random_system <a id="fn-make_random_system-26"></a>

*main.lua:26-36*

**Developer comment**

> Build n bodies at pseudo-random positions with small random velocities.

**Description**

Creates a table of n randomly generated Body objects with positions in [-10,10], small in-plane velocities in [-0.1,0.1], zero z-velocity, and masses in [1,2], using the given seed for reproducibility.

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of Body objects to create. |
| `seed` | Value passed to math.randomseed to initialise the PRNG. |

**Outputs**

| Name | Description |
| --- | --- |
| `bodies` | A table containing n newly constructed Body instances with random position, velocity, and mass. |

**Side effects**

- Sets the global Lua random-number-generator state via math.randomseed(seed).

**References**

- [Body](body.lua.md)
- math.randomseed
- math.random
- table.insert

**Uncertainties**

- The exact field names and semantics of the seven positional arguments accepted by Body:new (assumed to be x, y, z, vx, vy, vz, mass).
- Whether Body:new performs any additional internal initialisation beyond storing the given parameters.

```lua
local function make_random_system(n, seed)
  math.randomseed(seed)
  local bodies = {}
  for i = 1, n do
    table.insert(bodies, Body:new(
      math.random() * 20 - 10, math.random() * 20 - 10, math.random() * 20 - 10,
      math.random() * 0.2 - 0.1, math.random() * 0.2 - 0.1, 0,
      1 + math.random()))
  end
  return bodies
end
```

**Call graph**

- [main.lua](main.lua.md)
  - [main:51](main.lua.md#fn-main-46)

---

### tick <a id="fn-tick-39"></a>

*main.lua:39-44*

**Developer comment**

> Advance one frame: compute total energy, then integrate the bodies.

**Description**

Performs one tick of the N-body simulation by recording the current total energy, computing accelerations, advancing the bodies by the time step dt, and logging the energy value.

**Parameters**

| Name | Description |
| --- | --- |
| `sim` | Simulation object providing total_energy, accelerations, and step methods. |
| `bodies` | Collection of bodies whose positions/velocities are updated by the simulation step. |
| `dt` | Time-step duration used to integrate the bodies forward. |

**Side effects**

- Mutates the bodies collection via sim:accelerations and sim:step (updates positions/velocities).
- Writes a log line via log.info reporting the total energy.

**References**

- sim:total_energy
- sim:accelerations
- sim:step
- log.info
- tostring

**Uncertainties**

- The exact fields mutated on each body (e.g. position, velocity, acceleration) depend on the unseen implementations of sim:accelerations and sim:step.
- Whether sim:step also mutates the sim object's internal state is not visible here.

```lua
local function tick(sim, bodies, dt)
  local e = sim:total_energy(bodies)
  sim:accelerations(bodies)
  sim:step(bodies, dt)
  log.info("energy=" .. tostring(e))
end
```

**Call graph**

- [main.lua](main.lua.md)
  - [main:56](main.lua.md#fn-main-46)

---

### main <a id="fn-main-46"></a>

*main.lua:46-60*

**Description**

Initializes an N-body system (circular or random) based on the MODE setting, advances the simulation for RUNS timesteps using tick, and returns the total number of bodies in the system.

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The number of bodies in the simulation (length of the bodies table). |

**Side effects**

- Mutates the bodies table (positions/velocities) over RUNS iterations via tick.
- Reads system time via os.time() when generating the random system.

**References**

- [MODE](main.lua.md#variables)
- [make_circular_system](main.lua.md#fn-make_circular_system-12)
- [make_random_system](main.lua.md#fn-make_random_system-26)
- os.time
- [FPS](main.lua.md#variables)
- [RUNS](main.lua.md#variables)
- [tick](main.lua.md#fn-tick-39)
- [NBody](nbody.lua.md)

**Uncertainties**

- The value of MODE is not visible; it determines whether the circular (8 bodies) or random (12 bodies) system is created.
- The values of FPS and RUNS are not visible in this snippet.
- Whether tick mutates the bodies table in place or returns a modified copy is not visible.
- What the NBody module provides to tick (e.g., physics constants, solver) is not shown here.

```lua
local function main()
  local bodies
  if MODE == "circular" then
    bodies = make_circular_system(8)
  else
    bodies = make_random_system(12, os.time())
  end

  local dt = 1 / FPS
  for _ = 1, RUNS do
    tick(NBody, bodies, dt)
  end

  return #bodies
end
```

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `NBody` | 3 | call | Holds the main N-body simulation instance for the demo, created by calling a constructor or factory function at module load time. |
| `Body` | 4 | call | A body object instantiated via a function call, representing a single entity in the N-body simulation demo. |
| `log` | 5 | call | A variable initialized with the result of a function call, likely holding a logger or logging function used to emit diagnostic or debug outp … |
| `FPS` | 7 | number | A numeric value that sets the target frames-per-second rate for the N-body simulation loop, typically used to cap or throttle the update fre … |
| `RUNS` | 8 | number | A numeric value in main.lua that specifies the number of simulation runs (iterations) to execute in the N-body demo. |
| `MODE` | 9 | string | A file-level string variable in main.lua that holds the current simulation mode (e.g. a state label such as 'run' or 'pause'). It is read or … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
