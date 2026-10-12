# body.py

## Summary

Defines a Body class representing a single particle in an N-body simulation, storing 3D position, velocity, mass, and acceleration. Provides methods to initialize or reset state, integrate force into velocity (semi-implicit Euler step), and compute kinetic energy. Also declares the file-level constants G (gravitational constant) and SOFTENING (gravitational softening parameter) used by the simulation.
**Main purpose:** To model a single point-mass body with its kinematic state and basic dynamics operations for an N-body simulation.
**Role in project:** Serves as the core data structure and simple integrator for individual particles within the N-body simulation demo project.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [__init__](#fn-__init__-10) | 10 | self, x, y, z, vx, vy, vz, mass | Constructor for a Body object in an N-body simulation. Initializes the body's 3D position, velocity, mass, and sets acceleration components  … |
| [reset](#fn-reset-17) | 17 | self, x, y, z, vx, vy, vz | Resets the body's Cartesian position and velocity to the supplied values and zeroes out all three acceleration components. |
| [apply_force](#fn-apply_force-23) | 23 | self, fx, fy, fz, dt | Applies a constant force (fx, fy, fz) over a time step dt to update the body's velocity components according to F = ma. |
| [kinetic_energy](#fn-kinetic_energy-29) | 29 | self | Computes and returns the translational kinetic energy of a body using its mass and 3D velocity components (0.5 * m * v²). |

### __init__ <a id="fn-__init__-10"></a>

*body.py:10-14*

**Description**

Constructor for a Body object in an N-body simulation. Initializes the body's 3D position, velocity, mass, and sets acceleration components to zero.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance being initialized. |
| `x` | Initial x-coordinate of the body's position. |
| `y` | Initial y-coordinate of the body's position. |
| `z` | Initial z-coordinate of the body's position. |
| `vx` | Initial x-component of the body's velocity. |
| `vy` | Initial y-component of the body's velocity. |
| `vz` | Initial z-component of the body's velocity. |
| `mass` | Mass of the body. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Sets instance attributes: x, y, z, vx, vy, vz, mass, and ax, ay, az (initialized to 0.0). |

**Side effects**

- Mutates the instance by setting position (x, y, z), velocity (vx, vy, vz), mass, and acceleration (ax, ay, az) attributes.

**Uncertainties**

- The exact class name is not visible in the snippet (inferred to be 'Body' from the file name body.py).
- The physical units used for position, velocity, and mass are not specified in the code.

```py
def __init__(self, x, y, z, vx, vy, vz, mass):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.mass = mass
        self.ax, self.ay, self.az = 0.0, 0.0, 0.0
```

---

### reset <a id="fn-reset-17"></a>

*body.py:17-20*

**Developer comment**

> Reset the body state, keeping the same instance.

**Description**

Resets the body's Cartesian position and velocity to the supplied values and zeroes out all three acceleration components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose state is being reset. |
| `x` | New x-coordinate of the body's position. |
| `y` | New y-coordinate of the body's position. |
| `z` | New z-coordinate of the body's position. |
| `vx` | New x-component of the body's velocity. |
| `vy` | New y-component of the body's velocity. |
| `vz` | New z-component of the body's velocity. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No explicit return value (implicitly returns None). |

**Side effects**

- Sets self.x, self.y, self.z to the given position arguments.
- Sets self.vx, self.vy, self.vz to the given velocity arguments.
- Sets self.ax, self.ay, self.az to 0.0.

**Uncertainties**

- Other Body attributes (e.g. mass, radius, ID) are not touched by this method; their presence and whether a full reset would include them cannot be determined from this code alone.

```py
def reset(self, x, y, z, vx, vy, vz):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.ax, self.ay, self.az = 0.0, 0.0, 0.0
```

---

### apply_force <a id="fn-apply_force-23"></a>

*body.py:23-26*

**Developer comment**

> Apply a force over dt as an impulse: F*dt = m*dv.

**Description**

Applies a constant force (fx, fy, fz) over a time step dt to update the body's velocity components according to F = ma.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose velocity is updated. |
| `fx` | Force component along the x-axis. |
| `fy` | Force component along the y-axis. |
| `fz` | Force component along the z-axis. |
| `dt` | Time step (duration) over which the force is applied. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No return value (returns None). Velocity changes are reflected in mutated attributes. |

**Side effects**

- Mutates self.vx, self.vy, self.vz by adding force * dt / mass to each velocity component.

**References**

- self.mass

**Uncertainties**

- Whether mass could be zero, which would cause a division-by-zero error.

```py
def apply_force(self, fx, fy, fz, dt):
        self.vx += fx * dt / self.mass
        self.vy += fy * dt / self.mass
        self.vz += fz * dt / self.mass
```

---

### kinetic_energy <a id="fn-kinetic_energy-29"></a>

*body.py:29-31*

**Developer comment**

> Translational kinetic energy: 0.5*m*v^2.

**Description**

Computes and returns the translational kinetic energy of a body using its mass and 3D velocity components (0.5 * m * v²).

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose kinetic energy is calculated. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A float representing the kinetic energy (0.5 * mass * (vx² + vy² + vz²)). |

**References**

- [body.py](body.py.md)

```py
def kinetic_energy(self):
        v2 = self.vx * self.vx + self.vy * self.vy + self.vz * self.vz
        return 0.5 * self.mass * v2
```

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `G` | 3 | number | A numeric constant defined in body.py; given the N-body simulation context and conventional naming, it most likely holds the gravitational c … |
| `SOFTENING` | 4 | number | A numeric constant representing the gravitational softening parameter, used to regularize force calculations and avoid singularities when in … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
