# body.lua

## Summary

Defines the Body object for an N-body simulation, storing position, velocity, mass, and acceleration for a single celestial body. Provides methods to construct a new body (Body.new), reset its kinematic state (Body.reset), apply an external force over a time step to update velocity via F=ma (Body.apply_force), and compute its kinetic energy (Body.kinetic_energy). The file also declares file-level constants G (gravitational constant) and SOFTENING (a softening parameter for gravitational calculations).
**Main purpose:** Provides the fundamental Body class representing a single mass in the N-body simulation with methods for initialization, state reset, force integration, and kinetic-energy calculation.
**Role in project:** Serves as the core per-body data model and physics primitive that other modules in the simulation (e.g., force computation, integration loops, or rendering) operate on.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [Body.new](#fn-new-9) | 9 | self, x, y, z, vx, vy, vz, mass | Constructor that creates a new Body instance with the given position, velocity, and mass, initializing acceleration components to zero and s … |
| [Body.reset](#fn-reset-19) | 19 | self, x, y, z, vx, vy, vz | Resets the Body's position and velocity to the supplied values and zeroes its acceleration fields. |
| [Body.apply_force](#fn-apply_force-26) | 26 | self, fx, fy, fz, dt | Updates the body's velocity components (vx, vy, vz) by integrating an applied force over a time step, using the relation v += F * dt / m. |
| [Body.kinetic_energy](#fn-kinetic_energy-33) | 33 | self | Computes and returns the kinetic energy of the body using the standard 3D formula (1/2 * mass * v²), where v is the magnitude of the velocit … |

### Body.new <a id="fn-new-9"></a>

*body.lua:9-16*

**Developer comment**

> Create a body at (x,y,z) with velocity (vx,vy,vz) and the given mass.

**Description**

Constructor that creates a new Body instance with the given position, velocity, and mass, initializing acceleration components to zero and setting up the metatable for class inheritance.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body class table (passed implicitly via ':' syntax); used as the metatable __index target. |
| `x` | Initial x position coordinate. |
| `y` | Initial y position coordinate. |
| `z` | Initial z position coordinate. |
| `vx` | Initial x velocity component. |
| `vy` | Initial y velocity component. |
| `vz` | Initial z velocity component. |
| `mass` | Mass of the body. |

**Outputs**

| Name | Description |
| --- | --- |
| `self` | A new Body instance (a table) with position, velocity, mass, and zeroed acceleration fields. |

**References**

- [Body](body.lua.md)
- setmetatable

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

Resets the Body's position and velocity to the supplied values and zeroes its acceleration fields.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance being reset (implicit via colon syntax). |
| `x` | New x-coordinate position. |
| `y` | New y-coordinate position. |
| `z` | New z-coordinate position. |
| `vx` | New x-component of velocity. |
| `vy` | New y-component of velocity. |
| `vz` | New z-component of velocity. |

**Side effects**

- Mutates self.x, self.y, self.z to the supplied position values.
- Mutates self.vx, self.vy, self.vz to the supplied velocity values.
- Sets self.ax, self.ay, self.az to 0.

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

Updates the body's velocity components (vx, vy, vz) by integrating an applied force over a time step, using the relation v += F * dt / m.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose velocity is to be updated. |
| `fx` | Force component along the x-axis. |
| `fy` | Force component along the y-axis. |
| `fz` | Force component along the z-axis. |
| `dt` | Time step (duration over which the force is applied). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No return value; the function mutates self.vx, self.vy, and self.vz in place. |

**Side effects**

- Mutates self.vx, self.vy, and self.vz (the body's velocity state).

**References**

- Body.mass
- Body.vx
- Body.vy
- Body.vz

**Uncertainties**

- Whether self.mass is guaranteed to be non-zero at call time; division by zero is not guarded.
- The expected units or magnitude conventions for force components and dt are not stated in this snippet.

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

Computes and returns the kinetic energy of the body using the standard 3D formula (1/2 * mass * v²), where v is the magnitude of the velocity vector (vx, vy, vz).

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose kinetic energy is being computed (implicit via Lua colon syntax). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A numeric value equal to 0.5 * mass * (vx² + vy² + vz²), representing the body's kinetic energy. |

**References**

- [Body](body.lua.md)

**Uncertainties**

- Units of mass and velocity are not specified in the code; kinetic energy units depend on those choices.

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
| `G` | 3 | number | Numeric value representing the gravitational constant used in force calculations between bodies in the N-body simulation. |
| `SOFTENING` | 4 | number | A numeric softening parameter in the N-body simulation, used to regularize gravitational force calculations and prevent singularities when b … |
| `Body` | 6 | table | A table defined in body.lua that serves as the data structure or prototype for an individual body (e.g., position, velocity, mass) in the N- … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
