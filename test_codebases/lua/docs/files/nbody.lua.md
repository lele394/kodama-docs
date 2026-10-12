# nbody.lua

## Summary

Defines the NBody module containing the core physics routines for a 3D gravitational N-body simulation. It provides three methods: computing pairwise gravitational accelerations between bodies (with a minimum-distance cutoff to prevent singularities), performing a semi-implicit Euler integration step to advance velocities and positions, and calculating the total mechanical energy as the sum of kinetic and gravitational potential terms. The module relies on a global gravitational constant G, a vec3 helper library, and a MIN_DIST safety threshold.
**Main purpose:** Implements the gravitational physics—acceleration calculation, time-stepping integration, and total energy computation—for an N-body system.
**Role in project:** Acts as the physics engine module of the N-body simulation demo, supplying the core computational routines that drive gravitational interactions and system evolution.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [NBody.accelerations](#fn-accelerations-18) | 18 | self, bodies | Computes the gravitational acceleration for every pair of bodies in the supplied array using Newton's law of universal gravitation. Each bod … |
| [NBody.step](#fn-step-52) | 52 | self, bodies, dt | Advances the state of all bodies in the simulation by one time step using semi-implicit Euler integration: first updates velocities from acc … |
| [NBody.total_energy](#fn-total_energy-69) | 69 | self, bodies | Computes the total mechanical energy of an N-body system by summing the kinetic energy of every body and the pairwise gravitational potentia … |

### NBody.accelerations <a id="fn-accelerations-18"></a>

*nbody.lua:18-49*

**Developer comment**

> - Accumulates the pairwise gravitational acceleration of every body.
> - Uses a softened distance to avoid singularities at close range.

**Description**

Computes the gravitational acceleration for every pair of bodies in the supplied array using Newton's law of universal gravitation. Each body's ax, ay, az fields are first zeroed, then updated with the net pairwise acceleration (equal-and-opposite contributions from every other body), with the inter-body distance clamped to MIN_DIST to prevent division by zero.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The NBody instance; may carry the gravitational constant G or other simulation parameters. |
| `bodies` | Array of body tables (each with mass, position, and acceleration fields) to which pairwise gravitational accelerations are applied. |

**Outputs**

| Name | Description |
| --- | --- |
| `bodies` | The same bodies table, now with ax, ay, az fields populated with the computed net gravitational acceleration for each body. |

**Side effects**

- Mutates every body in the bodies array by writing to its ax, ay, and az fields.

**References**

- [MIN_DIST](nbody.lua.md#variables)
- math.sqrt

**Uncertainties**

- The exact gravitational constant G used in the formula is not visible; it may be stored on self or as a module-level constant.
- The numeric value of MIN_DIST is not shown in the summarized code.
- Whether self carries any other state (e.g., a softening parameter beyond MIN_DIST) is unknown.

```lua
function NBody:accelerations(bodies)
  local n = #bodies
  for i = 1, n do
    bodies[i].ax = 0
    bodies[i].ay = 0
    bodies[i].az = 0
  end

  for i = 1, n - 1 do
    for j = i + 1, n do
      local dx = bodies[j].x - bodies[i].x
      local dy = bodies[j].y - bodies[i].y
      local dz = bodies[j].z - bodies[i].z
      local d2 = dx * dx + dy * dy + dz * dz
      if d2 < MIN_DIST then
        d2 = MIN_DIST
      end
      local dist = math.sqrt(d2)
      local inv3 = 1.0 / (dist * d2)
      local fi = G * bodies[j].mass * inv3
      local fj = G * bodies[i].mass * inv3
      bodies[i].ax = bodies[i].ax + fi * dx
      bodies[i].ay = bodies[i].ay + fi * dy
      bodies[i].az = bodies[i].az + fi * dz
      bodies[j].ax = bodies[j].ax - fj * dx
      bodies[j].ay = bodies[j].ay - fj * dy
      bodies[j].az = bodies[j].az - fj * dz
    end
  end

  return bodies
end
```

**Call graph**

- [main.lua](main.lua.md)
  - [tick:41](main.lua.md#fn-tick-39)

---

### NBody.step <a id="fn-step-52"></a>

*nbody.lua:52-66*

**Developer comment**

> Semi-implicit Euler step: velocities from accelerations, then positions.

**Description**

Advances the state of all bodies in the simulation by one time step using semi-implicit Euler integration: first updates velocities from accumulated accelerations, then updates positions from the new velocities.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The NBody instance (method receiver). |
| `bodies` | Array of body objects, each carrying x/y/z position, vx/vy/vz velocity, and ax/ay/az acceleration fields. |
| `dt` | Time-step duration for the integration step. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No explicit return value; the function returns nil but mutates each element of the bodies array in place (x, y, z, vx, vy, vz). |

**Side effects**

- Mutates every body in the passed-in bodies array by updating its velocity components (vx, vy, vz) and then its position components (x, y, z).

**References**

- [NBody](nbody.lua.md)

**Uncertainties**

- Acceleration fields (ax, ay, az) are read but never set here; they are presumably computed by the caller (tick) or another function before step is invoked.
- Whether the two-loop structure (all velocities before all positions) is intentional to avoid order-dependent coupling or simply a readability choice.

```lua
function NBody:step(bodies, dt)
  for i = 1, #bodies do
    local b = bodies[i]
    b.vx = b.vx + b.ax * dt
    b.vy = b.vy + b.ay * dt
    b.vz = b.vz + b.az * dt
  end

  for i = 1, #bodies do
    local b = bodies[i]
    b.x = b.x + b.vx * dt
    b.y = b.y + b.vy * dt
    b.z = b.z + b.vz * dt
  end
end
```

**Call graph**

- [main.lua](main.lua.md)
  - [tick:42](main.lua.md#fn-tick-39)

---

### NBody.total_energy <a id="fn-total_energy-69"></a>

*nbody.lua:69-85*

**Developer comment**

> Total mechanical energy: kinetic plus pairwise potential.

**Description**

Computes the total mechanical energy of an N-body system by summing the kinetic energy of every body and the pairwise gravitational potential energy between all unique body pairs.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The NBody instance (implicit method receiver); not directly used in the body of the function. |
| `bodies` | Array of body objects, each expected to expose x, y, z, mass fields and a kinetic_energy() method. |

**Outputs**

| Name | Description |
| --- | --- |
| `e` | Total energy: sum of all bodies' kinetic energies plus the sum of -G*m_i*m_j/d over all unique pairs (i<j). |

**References**

- vec3.length
- vec3.sub
- [G](nbody.lua.md#variables)
- [NBody.total_energy](nbody.lua.md#fn-total_energy-69)
- bodies[i]:kinetic_energy

**Uncertainties**

- The implementation of kinetic_energy() on individual body objects is not visible.
- G is referenced as a global constant but its definition is not shown in this snippet.
- The full structure of body objects (e.g., whether mass is a number or a method) is inferred only from usage.

```lua
function NBody:total_energy(bodies)
  local e = 0
  for i = 1, #bodies do
    e = e + bodies[i]:kinetic_energy()
  end

  for i = 1, #bodies - 1 do
    for j = i + 1, #bodies do
      local d = vec3.length(vec3.sub(
        { bodies[j].x, bodies[j].y, bodies[j].z },
        { bodies[i].x, bodies[i].y, bodies[i].z }))
      e = e - G * bodies[i].mass * bodies[j].mass / d
    end
  end

  return e
end
```

**Call graph**

- [main.lua](main.lua.md)
  - [tick:40](main.lua.md#fn-tick-39)

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `vec3` | 3 | call | File-level reference in the N-body simulation module, initialized by a function call, likely providing 3D vector operations (position, veloc … |
| `G` | 5 | number | Numeric constant representing the gravitational constant used in the N-body simulation's force calculations between bodies. |
| `MIN_DIST` | 6 | number | A numeric constant in nbody.lua that defines a minimum distance threshold, typically used to clamp pairwise body separations and avoid divis … |
| `NBody` | 8 | table | A table that holds the state data (such as position, velocity, mass) of a body within the N-body simulation. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
