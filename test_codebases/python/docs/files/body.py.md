# body.py

## Summary

Defines a Body class representing a single particle in an N-body gravitational simulation, storing position, velocity, mass, and acceleration. Provides methods to initialize or reset state, integrate an applied force into velocity over a time step, and compute kinetic energy. Also declares module-level constants G (gravitational constant) and SOFTENING (force-softening parameter) for use by other parts of the simulation.
**Main purpose:** To encapsulate the state and basic dynamics of a single body in an N-body simulation.
**Role in project:** Serves as the fundamental data-and-behavior unit that other simulation modules (e.g., force calculation, integration loop, visualization) operate on.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [__init__](#fn-__init__-10) | 10 | self, x, y, z, vx, vy, vz, mass | Initializes a Body instance with a 3D position, 3D velocity, and mass, and sets all acceleration components to zero. |
| [reset](#fn-reset-17) | 17 | self, x, y, z, vx, vy, vz | Resets the body's position to the given (x, y, z) coordinates, sets its velocity to (vx, vy, vz), and zeroes out all acceleration components … |
| [apply_force](#fn-apply_force-23) | 23 | self, fx, fy, fz, dt | Updates the body's velocity components (vx, vy, vz) by applying a given force vector over a time step, using Newton's second law (Δv = F·dt  … |
| [kinetic_energy](#fn-kinetic_energy-29) | 29 | self | Computes the kinetic energy of the body as 0.5 * mass * \|v\|², where \|v\|² is the sum of the squared velocity components (vx, vy, vz). |

### __init__ <a id="fn-__init__-10"></a>

*body.py:10-14*

**Description**

Initializes a Body instance with a 3D position, 3D velocity, and mass, and sets all acceleration components to zero.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance being initialized. |
| `x` | Initial x-coordinate of the body's position. |
| `y` | Initial y-coordinate of the body's position. |
| `z` | Initial z-coordinate of the body's position. |
| `vx` | Initial velocity component along the x-axis. |
| `vy` | Initial velocity component along the y-axis. |
| `vz` | Initial velocity component along the z-axis. |
| `mass` | Mass of the body. |

**Side effects**

- Sets instance attributes x, y, z (position).
- Sets instance attributes vx, vy, vz (velocity).
- Sets instance attribute mass.
- Sets instance attributes ax, ay, az to 0.0 (initial acceleration).

**Uncertainties**

- The exact class name is inferred as 'Body' from the filename body.py, but is not explicitly stated in the shown snippet.

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

Resets the body's position to the given (x, y, z) coordinates, sets its velocity to (vx, vy, vz), and zeroes out all acceleration components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose state is being reset. |
| `x` | New x-position coordinate. |
| `y` | New y-position coordinate. |
| `z` | New z-position coordinate. |
| `vx` | New x-component of velocity. |
| `vy` | New y-component of velocity. |
| `vz` | New z-component of velocity. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | No explicit return value; implicitly returns None. |

**Side effects**

- Sets self.x, self.y, self.z to the provided position values.
- Sets self.vx, self.vy, self.vz to the provided velocity values.
- Sets self.ax, self.ay, self.az to 0.0.

**Uncertainties**

- The class may have additional attributes (e.g., mass) that are not modified or shown here.
- Units and coordinate system conventions for the position and velocity parameters are not specified in the code.

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

Updates the body's velocity components (vx, vy, vz) by applying a given force vector over a time step, using Newton's second law (Δv = F·dt / m).

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Body instance whose velocity is being modified. |
| `fx` | Force magnitude in the x-axis (presumably in Newtons). |
| `fy` | Force magnitude in the y-axis (presumably in Newtons). |
| `fz` | Force magnitude in the z-axis (presumably in Newtons). |
| `dt` | Time-step duration over which the force is applied. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Returns None implicitly; effect is the in-place mutation of self.vx, self.vy, and self.vz. |

**Side effects**

- Mutates self.vx, self.vy, and self.vz by adding fx*dt/mass, fy*dt/mass, and fz*dt/mass respectively.

**References**

- self.mass
- self.vx
- self.vy
- self.vz

**Uncertainties**

- The type and units of self.mass are not visible in this snippet.
- No guard against self.mass being zero is present in this code.

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

Computes the kinetic energy of the body as 0.5 * mass * \|v\|², where \|v\|² is the sum of the squared velocity components (vx, vy, vz).

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The body instance providing mass and velocity components. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A scalar representing the kinetic energy (0.5 * mass * (vx² + vy² + vz²)). |

```py
def kinetic_energy(self):
        v2 = self.vx * self.vx + self.vy * self.vy + self.vz * self.vz
        return 0.5 * self.mass * v2
```

**Call graph**

- [nbody.py](nbody.py.md)
  - [total_energy:63](nbody.py.md#fn-total_energy-62)

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `G` | 3 | number | A numeric constant representing the gravitational constant, used in computing pairwise gravitational forces within the N-body simulation. |
| `SOFTENING` | 4 | number | A numeric constant representing the softening parameter for the N-body simulation, used to regularize force calculations and avoid singulari … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
