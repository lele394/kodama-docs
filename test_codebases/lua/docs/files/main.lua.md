# main.lua

## Summary

This is the main entry-point script for a small N-body gravity simulation demo. It defines two system constructors (circular orbits around a central mass and random placement), a tick function that records total energy, computes accelerations, and steps the simulation forward by dt, and a main function that selects the mode, runs a fixed number of ticks, and returns the body count.
**Main purpose:** Provides the top-level driver that assembles an N-body system and executes a fixed number of simulation ticks.
**Role in project:** Serves as the executable entry point of the demo project, wiring together the NBody simulator, Body class, and logging utilities into a runnable loop.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [make_circular_system](#fn-make_circular_system-12) | 12 | n | Constructs a table of Body objects representing an N-body system with one massive central body at the origin and n smaller bodies placed at  … |
| [make_random_system](#fn-make_random_system-26) | 26 | n, seed | Creates a table of n randomly-generated Body objects by seeding the pseudo-random number generator and constructing each body with random po … |
| [tick](#fn-tick-39) | 39 | sim, bodies, dt | Advances the N-body simulation by one time step: computes total energy, updates accelerations, integrates positions/velocities by dt, and lo … |
| [main](#fn-main-46) | 46 |  | Initialises an N-body system (circular or random based on the global MODE), then advances it for a fixed number of integration steps and ret … |

### make_circular_system <a id="fn-make_circular_system-12"></a>

*main.lua:12-23*

**Developer comment**

> Build n bodies on a circular orbit around a central mass of 1000.

**Description**

Constructs a table of Body objects representing an N-body system with one massive central body at the origin and n smaller bodies placed at evenly-spaced angles on circles of increasing radius, each assigned a tangential orbital velocity.

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of orbiting bodies to create around the central body (does not include the central body itself). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A Lua table containing n+1 Body instances: one central body (mass 1000, at origin) followed by n orbiting bodies (mass 1, positioned on a circle of radius 10+2i with tangential speed sqrt(1000/r)). |

**References**

- [Body](main.lua.md#variables)
- math.sqrt
- math.cos
- math.sin
- math.pi
- table.insert

**Uncertainties**

- The full constructor signature of Body is not visible; it is inferred that the 7 arguments are (x, y, z, vx, vy, vz, mass) but this is not confirmed in the snippet.
- Whether Body:new performs any additional initialization (e.g., assigning an id, registering in a global list) is not visible here.

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

Creates a table of n randomly-generated Body objects by seeding the pseudo-random number generator and constructing each body with random position, velocity, and mass values, then returns the resulting table.

**Parameters**

| Name | Description |
| --- | --- |
| `n` | Number of Body objects to generate. |
| `seed` | Seed value passed to math.randomseed to make the random generation reproducible. |

**Outputs**

| Name | Description |
| --- | --- |
| `bodies` | A Lua table containing n Body instances, each with random position (x, y, z in [-10, 10]), velocity (vx, vy in [-0.1, 0.1], vz = 0), and mass in [1, 2]. |

**Side effects**

- Sets the global pseudo-random number generator state via math.randomseed(seed).
- Constructs n Body instances via Body:new (which may perform its own internal initialization).

**References**

- math.randomseed
- table.insert
- [Body](main.lua.md#variables)
- math.random

**Uncertainties**

- The exact constructor parameter order and semantics of Body:new are not shown in this file; the mapping of the 7 positional arguments (pos x/y/z, vel x/y/z, mass) is inferred from value ranges.
- Whether Body:new registers instances in a global registry or triggers other side effects beyond object construction is not visible here.
- The type and expected range of seed (e.g., integer vs. arbitrary number) is not documented in this snippet.

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

Advances the N-body simulation by one time step: computes total energy, updates accelerations, integrates positions/velocities by dt, and logs the energy value.

**Parameters**

| Name | Description |
| --- | --- |
| `sim` | Simulation object providing total_energy, accelerations, and step methods. |
| `bodies` | Collection (table) of body objects representing the particles in the system. |
| `dt` | Time-step delta used to advance the simulation. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No explicit return value; the function is used for its side effects on bodies and logging. |

**Side effects**

- Mutates the bodies collection via sim:accelerations and sim:step (positions, velocities, accelerations are likely updated).
- Writes a log line via log.info containing the total energy of the system.

**References**

- sim:total_energy
- sim:accelerations
- sim:step
- log.info

**Uncertainties**

- Whether sim:step mutates bodies in-place or replaces entries is not visible in this function.
- The exact structure of the bodies collection (array vs. keyed table) is not shown here.
- Whether log.info writes to stdout, a file, or a ring buffer depends on the log module implementation.

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

Initialises an N-body system (circular or random based on the global MODE), then advances it for a fixed number of integration steps and returns the number of bodies created.

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The number of bodies in the system (8 for circular mode, 12 for random mode), i.e. the length of the bodies table. |

**Side effects**

- Calls tick(NBody, bodies, dt) in a loop, which presumably mutates the bodies' state (positions, velocities) over RUNS iterations.

**References**

- [MODE](main.lua.md#variables)
- [make_circular_system](main.lua.md#fn-make_circular_system-12)
- [make_random_system](main.lua.md#fn-make_random_system-26)
- [FPS](main.lua.md#variables)
- [RUNS](main.lua.md#variables)
- [NBody](main.lua.md#variables)
- [tick](main.lua.md#fn-tick-39)
- os.time

**Uncertainties**

- The exact values of the globals MODE, FPS, and RUNS are not visible in this snippet.
- What NBody is (a module table, a class, or a namespace) is not determined here.
- Whether tick mutates bodies in-place or replaces them is not visible from this code alone.

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
| `NBody` | 3 | call | A module reference loaded via a call (likely `require`) on line 3 of `main.lua`, providing access to the N-body simulation logic used by thi … |
| `Body` | 4 | call | A local variable in main.lua, line 4, initialized via a function call, representing a body entity used in the N-body simulation. |
| `log` | 5 | call | A local variable in main.lua (line 5) assigned the result of a function call, most likely a logging utility or logger instance used for outp … |
| `FPS` | 7 | number | A numeric variable holding the frames-per-second value for the N-body simulation, likely used as a target or cap for the update/render loop. |
| `RUNS` | 8 | number | A numeric value in main.lua that specifies the number of simulation runs (iterations) to execute in the N-body demo. |
| `MODE` | 9 | string | A string variable in main.lua that stores the current mode identifier for the N-body simulation demo. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
