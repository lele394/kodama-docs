# nbody.py

## Summary

nbody.py implements the core physics routines for an N-body gravitational simulation. It defines a class with three methods: `accelerations` (pairwise gravitational acceleration computation with a minimum-distance clamp), `step` (Euler integration of velocities and positions), and `total_energy` (sum of kinetic and pairwise gravitational potential energies). Module-level constants G, MIN_DIST, and PARAMS supply the gravitational constant, softening distance, and simulation parameters used by these methods.
**Main purpose:** To provide the gravitational force calculation, time-step integration, and energy computation for a multi-body simulation.
**Role in project:** Core physics engine of the N-body simulation project, supplying the numerical methods that advance the state of all bodies and track system energy.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [accelerations](#fn-accelerations-22) | 22 | self, bodies | Resets the ax, ay, and az components of every body in the bodies list to zero, then iterates over all unique body pairs to compute pairwise  … |
| [step](#fn-step-50) | 50 | self, bodies, dt | Performs one semi-implicit (symplectic) Euler integration step: first updates each body's velocity from its acceleration, then updates each  … |
| [total_energy](#fn-total_energy-62) | 62 | self, bodies | Computes the total mechanical energy of an N-body system by summing the kinetic energy of all bodies and subtracting the pairwise gravitatio … |

### accelerations <a id="fn-accelerations-22"></a>

*nbody.py:22-47*

**Developer comment**

> Accumulates the pairwise gravitational acceleration of every body.
> Uses a softened distance to avoid singularities at close range.

**Description**

Resets the ax, ay, and az components of every body in the bodies list to zero, then iterates over all unique body pairs to compute pairwise gravitational accelerations via Newton's law of universal gravitation, clamping the squared distance to MIN_DIST to avoid division by zero, and applies equal-and-opposite acceleration updates to both bodies in place.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The simulation instance (provides access to constants such as the gravitational constant or MIN_DIST). |
| `bodies` | A list of body objects, each carrying mass, position (x, y, z), and acceleration (ax, ay, az) attributes. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The same bodies list is returned, with each body's ax, ay, and az attributes mutated to reflect the summed pairwise gravitational accelerations. |

**Side effects**

- Mutates the ax, ay, and az attributes of every body object in the bodies list (first zeroed, then updated with pairwise gravitational terms).
- Writes equal-and-opposite acceleration contributions for each body pair directly into the body objects.

**References**

- [MIN_DIST](nbody.py.md#variables)
- math
- [tick](main.py.md#fn-tick-43)
- len
- range

**Uncertainties**

- Whether the gravitational constant G is read from self, a module-level constant, or a class attribute.
- The exact numeric value of MIN_DIST and whether it is a class attribute, module constant, or local default.
- Whether bodies is expected to be a list or any sequence, and the exact class/structure of individual body objects.
- Whether the method handles a single-body or empty-list edge case explicitly beyond the loop bounds.

```py
def accelerations(self, bodies):
        for b in bodies:
            b.ax = b.ay = b.az = 0.0

        n = len(bodies)
        for i in range(n - 1):
            for j in range(i + 1, n):
                bi, bj = bodies[i], bodies[j]
                dx = bj.x - bi.x
                dy = bj.y - bi.y
                dz = bj.z - bi.z
                d2 = dx * dx + dy * dy + dz * dz
                if d2 < MIN_DIST:
                    d2 = MIN_DIST
                dist = math.sqrt(d2)
                inv3 = 1.0 / (dist * d2)
                fi = G * bj.mass * inv3
                fj = G * bi.mass * inv3
                bi.ax += fi * dx
                bi.ay += fi * dy
                bi.az += fi * dz
                bj.ax -= fj * dx
                bj.ay -= fj * dy
                bj.az -= fj * dz

        return bodies
```

**Call graph**

- [main.py](main.py.md)
  - [tick:45](main.py.md#fn-tick-43)

---

### step <a id="fn-step-50"></a>

*nbody.py:50-59*

**Developer comment**

> Semi-implicit Euler step: velocities from accelerations, then positions.

**Description**

Performs one semi-implicit (symplectic) Euler integration step: first updates each body's velocity from its acceleration, then updates each body's position from its new velocity, over a time step dt.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The integrator instance on which the method is called. |
| `bodies` | Iterable of body objects, each carrying x/y/z position, vx/vy/vz velocity, and ax/ay/az acceleration attributes. |
| `dt` | Time-step duration used to scale the velocity and position updates. |

**Side effects**

- Mutates vx, vy, vz (velocity) attributes of every body in bodies using the body's acceleration multiplied by dt.
- Mutates x, y, z (position) attributes of every body in bodies using the body's (newly updated) velocity multiplied by dt.

**Uncertainties**

- The concrete class of the body objects is not visible in this snippet; assumed to be a project-local Body or similar class.
- Whether dt is expressed in seconds or an arbitrary simulation unit is not stated in the code.
- Whether accelerations (ax, ay, az) are expected to be set externally before calling step is not shown here.

```py
def step(self, bodies, dt):
        for b in bodies:
            b.vx += b.ax * dt
            b.vy += b.ay * dt
            b.vz += b.az * dt

        for b in bodies:
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.z += b.vz * dt
```

**Call graph**

- [main.py](main.py.md)
  - [tick:46](main.py.md#fn-tick-43)

---

### total_energy <a id="fn-total_energy-62"></a>

*nbody.py:62-72*

**Developer comment**

> Total mechanical energy: kinetic plus pairwise potential.

**Description**

Computes the total mechanical energy of an N-body system by summing the kinetic energy of all bodies and subtracting the pairwise gravitational potential energy.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The instance of the class containing this method (implicit). |
| `bodies` | A collection (e.g. list) of body objects, each having x, y, z, mass attributes and a kinetic_energy() method. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A numeric value (float) representing the total energy: sum of kinetic energies minus sum of pairwise gravitational potential energies (G*m_i*m_j/d). |

**References**

- [kinetic_energy](body.py.md#fn-kinetic_energy-29)
- Vec3
- [G](nbody.py.md#variables)

**Uncertainties**

- The value and scope of the gravitational constant G (module-level or class-level) are not visible in this snippet.
- The exact container type of `bodies` (list, tuple, etc.) is not specified.
- The implementation of `kinetic_energy()` on body objects is not shown.
- Whether bodies is mutated or merely iterated cannot be confirmed beyond the visible read-only access.

```py
def total_energy(self, bodies):
        e = sum(b.kinetic_energy() for b in bodies)

        n = len(bodies)
        for i in range(n - 1):
            for j in range(i + 1, n):
                bi, bj = bodies[i], bodies[j]
                d = Vec3(bj.x - bi.x, bj.y - bi.y, bj.z - bi.z).length()
                e -= G * bi.mass * bj.mass / d

        return e
```

**Call graph**

- [main.py](main.py.md)
  - [tick:44](main.py.md#fn-tick-43)

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `G` | 7 | number | Holds the gravitational constant used in the N-body simulation, typically multiplied with mass terms to compute pairwise gravitational force … |
| `MIN_DIST` | 8 | number | A numeric constant in the N-body simulation that defines a minimum distance threshold, typically used to avoid singularities in pairwise for … |
| `PARAMS` | 10 | table | A table-like collection of simulation parameters used by the N-body simulation in nbody.py. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
