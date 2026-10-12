# body.lua

## Summary

This file defines a Body class for an N-body simulation, providing a constructor (Body.new) that stores position, velocity, mass, and zeroed acceleration, a reset method, a method to apply an external force over a time step (Body.apply_force), and a method to compute kinetic energy (Body.kinetic_energy). It also declares file-level constants G (gravitational constant) and SOFTENING (gravitational softening parameter), which are presumably used by other modules for pairwise force calculations.
**Main purpose:** To encapsulate the state and basic dynamics of a single simulated body (position, velocity, mass, and force application).
**Role in project:** Serves as the core data-and-dynamics object for each particle in the N-body simulation, referenced by force-calculation and integration modules.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [Body.new](#fn-new-9) | 9 | self, x, y, z, vx, vy, vz, mass | Constructor for a Body object in the N-body simulation. Creates a new table with position, velocity, and mass fields initialised from the ar … |
| [Body.reset](#fn-reset-19) | 19 | self, x, y, z, vx, vy, vz | Resets the position, velocity, and acceleration of a Body instance to the supplied coordinate and velocity values, zeroing all acceleration  … |
| [Body.apply_force](#fn-apply_force-26) | 26 | self, fx, fy, fz, dt | Applies a force vector (fx, fy, fz) over a time step dt to the body by updating its velocity components according to F = m·a, assuming a sim … |
| [Body.kinetic_energy](#fn-kinetic_energy-33) | 33 | self | Calculates and returns the kinetic energy of the body using the standard formula 0.5 * mass * (vx² + vy² + vz²). |

### Body.new <a id="fn-new-9"></a>

*body.lua:9-16*

**Developer comment**

> Create a body at (x,y,z) with velocity (vx,vy,vz) and the given mass.

**Description**

Constructor for a Body object in the N-body simulation. Creates a new table with position, velocity, and mass fields initialised from the arguments, sets acceleration components to zero, and returns the instance with Body as its metatable.

**Parameters**

| Name | Description |
| --- | --- |
| `x` | Initial x-coordinate of the body. |
| `y` | Initial y-coordinate of the body. |
| `z` | Initial z-coordinate of the body. |
| `vx` | Initial velocity in the x-axis. |
| `vy` | Initial velocity in the y-axis. |
| `vz` | Initial velocity in the z-axis. |
| `mass` | Mass of the body. |

**Outputs**

| Name | Description |
| --- | --- |
| `self` | A new Body instance (a plain table with Body as its metatable) carrying x, y, z, vx, vy, vz, mass, and zeroed ax, ay, az fields. |

**References**

- [Body](body.lua.md)
- setmetatable

**Uncertainties**

- Whether other methods on Body (e.g., a step or force-accumulation method) expect ax/ay/az to be pre-initialised to zero here or whether this is merely defensive.

```lua
function Body:new(x, y, z, vx, vy, vz, mass)
  local self = setmetatable({}, { __index = Body })
  self.x, self.y, self.z = x, y, z
  self.vx, self.vy, self.vz = vx, vy, vz
  self.mass = mass
  self.ax, self.ay, self.az = 0, 0, 0
  return self
end
```

**Call graph**

- [main.lua](main.lua.md)
  - [make_circular_system:13](main.lua.md#fn-make_circular_system-12)
  - [make_circular_system:18](main.lua.md#fn-make_circular_system-12)
  - [make_random_system:30](main.lua.md#fn-make_random_system-26)

---

### Body.reset <a id="fn-reset-19"></a>

*body.lua:19-23*

**Developer comment**

> Reset the body state, keeping the same table instance.

**Description**

Resets the position, velocity, and acceleration of a Body instance to the supplied coordinate and velocity values, zeroing all acceleration components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance to reset. |
| `x` | New x position coordinate. |
| `y` | New y position coordinate. |
| `z` | New z position coordinate. |
| `vx` | New x velocity component. |
| `vy` | New y velocity component. |
| `vz` | New z velocity component. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Returns no explicit value (implicit nil in Lua). |

**Side effects**

- Mutates the self body object by overwriting its x, y, z, vx, vy, vz, ax, ay, and az fields.

**References**

- [Body](body.lua.md)

```lua
function Body:reset(x, y, z, vx, vy, vz)
  self.x, self.y, self.z = x, y, z
  self.vx, self.vy, self.vz = vx, vy, vz
  self.ax, self.ay, self.az = 0, 0, 0
end
```

---

### Body.apply_force <a id="fn-apply_force-26"></a>

*body.lua:26-30*

**Developer comment**

> Apply a force over dt as an impulse: F*dt = m*dv.

**Description**

Applies a force vector (fx, fy, fz) over a time step dt to the body by updating its velocity components according to F = m·a, assuming a simple Euler integration step.

**Parameters**

| Name | Description |
| --- | --- |
| `fx` | Force component along the x-axis applied to the body. |
| `fy` | Force component along the y-axis applied to the body. |
| `fz` | Force component along the z-axis applied to the body. |
| `dt` | Time step (duration) over which the force is applied. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No value is returned; the function mutates the body's velocity in place. |

**Side effects**

- Mutates self.vx by adding fx * dt / self.mass.
- Mutates self.vy by adding fy * dt / self.mass.
- Mutates self.vz by adding fz * dt / self.mass.

**References**

- [Body](body.lua.md)

**Uncertainties**

- Units of mass, force, and dt are not specified in this snippet.
- Whether this is part of a larger integrator (e.g., velocity Verlet) or a standalone Euler step cannot be confirmed from this function alone.
- Whether self.mass can be zero or negative is not guarded here.

```lua
function Body:apply_force(fx, fy, fz, dt)
  self.vx = self.vx + fx * dt / self.mass
  self.vy = self.vy + fy * dt / self.mass
  self.vz = self.vz + fz * dt / self.mass
end
```

---

### Body.kinetic_energy <a id="fn-kinetic_energy-33"></a>

*body.lua:33-37*

**Developer comment**

> Translational kinetic energy: 0.5*m*v^2.

**Description**

Calculates and returns the kinetic energy of the body using the standard formula 0.5 * mass * (vx² + vy² + vz²).

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose mass and velocity components are used. |

**Outputs**

| Name | Description |
| --- | --- |
| `return` | A numeric value equal to 0.5 * mass * (vx² + vy² + vz²), representing the body's kinetic energy. |

**Uncertainties**

- Whether mass and velocity components are expected to be positive; the formula assumes standard SI-style units but no validation is visible.

```lua
function Body:kinetic_energy()
  return 0.5 * self.mass * (self.vx * self.vx
                            + self.vy * self.vy
                            + self.vz * self.vz)
end
```

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `G` | 3 | number | A numeric constant (likely the gravitational constant) defined at module level in body.lua for use in the N-body simulation's force calculat … |
| `SOFTENING` | 4 | number | A numeric softening constant used in the N-body simulation to avoid zero-division singularities when computing pairwise gravitational forces … |
| `Body` | 6 | table | A table defined in body.lua that serves as the class or module table for body (celestial object) definitions in the N-body simulation demo. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
