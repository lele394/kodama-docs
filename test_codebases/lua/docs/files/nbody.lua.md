# nbody.lua

## Summary

nbody.lua defines the NBody module containing the core physics computations for a gravitational N-body simulation. It provides three methods: accelerations (pairwise gravitational acceleration with a MIN_DIST softening floor), step (a semi-implicit Euler integrator that updates velocities then positions), and total_energy (sum of kinetic and pairwise potential energy). The file also declares shared constants G and MIN_DIST and depends on an external vec3 helper for vector operations.
**Main purpose:** To implement the gravitational force calculation, time-stepping, and energy computation for a small N-body system.
**Role in project:** Serves as the core physics module of the demo project, supplying the force model and integrator that a driver or visualization layer would call to advance the simulation.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [NBody.accelerations](#fn-accelerations-18) | 18 | self, bodies | Computes pairwise gravitational accelerations for every body using Newton's inverse-square law, applying Newton's third law so each pair of  … |
| [NBody.step](#fn-step-52) | 52 | self, bodies, dt | Advances an array of N-body particles by one time step using semi-implicit Euler integration, first updating velocities from accelerations a … |
| [NBody.total_energy](#fn-total_energy-69) | 69 | self, bodies | Computes the total energy of an N-body system by summing the kinetic energy of each body and the negative gravitational potential energy bet … |

### NBody.accelerations <a id="fn-accelerations-18"></a>

*nbody.lua:18-49*

**Developer comment**

> - Accumulates the pairwise gravitational acceleration of every body.
> - Uses a softened distance to avoid singularities at close range.

**Description**

Computes pairwise gravitational accelerations for every body using Newton's inverse-square law, applying Newton's third law so each pair of bodies receives equal-and-opposite updates to their ax, ay, and az fields in place, with a MIN_DIST floor on the squared distance to prevent singularities.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The NBody table (object) on which this method is called; carries configuration or constants such as MIN_DIST. |
| `bodies` | Array of body objects, each expected to have position (x, y, z), mass, and acceleration (ax, ay, az) fields. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Returns the same `bodies` table with all bodies' ax, ay, and az fields populated (zeroed first, then filled with the net gravitational acceleration). |

**Side effects**

- Mutates each body's ax, ay, and az fields in place (zeroed at the start, then accumulated over all pairs).

**References**

- [MIN_DIST](nbody.lua.md#variables)
- math.sqrt

**Uncertainties**

- The exact role of math.sqrt in the force computation (e.g., computing distance from squared distance for the unit direction vector) is inferred, not directly visible.
- Whether `self` is used to look up MIN_DIST or a gravitational constant G, or whether those are globals.
- The exact structure of each body object beyond x, y, z, mass, ax, ay, az is not confirmed by the summary alone.

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

Advances an array of N-body particles by one time step using semi-implicit Euler integration, first updating velocities from accelerations and then updating positions from the new velocities.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The NBody instance (method receiver). |
| `bodies` | Array of body objects, each having x, y, z, vx, vy, vz, ax, ay, az numeric fields. |
| `dt` | Time-step size for the integration update. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No explicit return value; the function mutates the bodies array in place. |

**Side effects**

- Mutates each body's velocity components (vx, vy, vz) by adding acceleration times dt.
- Mutates each body's position components (x, y, z) by adding the updated velocity times dt.

**Uncertainties**

- The exact structure/type of each body object is not defined in this snippet; field names are inferred from usage.
- Whether the function is intended to be called at a fixed or variable dt is not clear from this code alone.
- No return value is explicitly declared; it is assumed to return nil as is typical in Lua when no return statement is present.

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

Computes the total energy of an N-body system by summing the kinetic energy of each body and the negative gravitational potential energy between every unique pair of bodies.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The NBody instance (implicit receiver via colon call syntax); not directly used in the body. |
| `bodies` | Array of body objects, each exposing x, y, z, mass fields and a kinetic_energy() method. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A number representing the total energy: sum of all kinetic energies minus the sum of G*m_i*m_j/d over all pairs. |

**References**

- vec3.length
- vec3.sub
- [G](nbody.lua.md#variables)
- bodies[i].kinetic_energy

**Uncertainties**

- The value and origin of the global constant G (gravitational constant) are not defined in this snippet.
- The exact interface of body objects (kinetic_energy method signature, field layout) is inferred only from usage here.

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
| `vec3` | 3 | call | A 3D vector type or factory produced by a function call, used as the basic vector representation for positions, velocities, or accelerations … |
| `G` | 5 | number | Holds the gravitational constant (G) used in the N-body simulation to compute pairwise gravitational forces between bodies. |
| `MIN_DIST` | 6 | number | A numeric constant representing the minimum distance threshold used in the N-body simulation, typically to avoid singularities or numerical  … |
| `NBody` | 8 | table | A table in nbody.lua that serves as the container for body data (e.g., positions, velocities, masses) used in the N-body simulation. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
