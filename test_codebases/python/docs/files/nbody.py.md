# nbody.py

## Summary

Defines three methods—accelerations, step, and total_energy—that form the core physics of an N-body gravitational simulation. The accelerations method computes pairwise gravitational forces with a MIN_DIST softening threshold, step applies a simple velocity-then-position Euler integration over a time step dt, and total_energy sums kinetic and pairwise potential energies for conservation checks. Module-level constants G, MIN_DIST, and PARAMS configure the gravitational constant, softening distance, and simulation parameters.
**Main purpose:** Implements the gravitational force calculation, time-integration step, and total energy computation for an N-body system.
**Role in project:** Acts as the core physics computation module within the N-body simulation demo, providing the routines that advance body states and verify energy conservation.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [accelerations](#fn-accelerations-22) | 22 | self, bodies | Computes the gravitational acceleration on every body in the simulation by iterating over all unique pairs, applying Newton's law of univers … |
| [step](#fn-step-50) | 50 | self, bodies, dt | Advances each body in the simulation by one time step using a semi-implicit (symplectic) Euler integrator: first updates velocities from acc … |
| [total_energy](#fn-total_energy-62) | 62 | self, bodies | Computes the total energy of a system of N bodies by summing their individual kinetic energies and subtracting the pairwise gravitational po … |

### accelerations <a id="fn-accelerations-22"></a>

*nbody.py:22-47*

**Developer comment**

> Accumulates the pairwise gravitational acceleration of every body.
> Uses a softened distance to avoid singularities at close range.

**Description**

Computes the gravitational acceleration on every body in the simulation by iterating over all unique pairs, applying Newton's law of universal gravitation with equal-and-opposite contributions (Newton's third law), and writing the results directly into each body's acceleration components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The NBody simulation instance, providing access to the gravitational constant G and possibly MIN_DIST. |
| `bodies` | A list of body objects, each carrying position (x, y, z), mass, and acceleration (ax, ay, az) attributes. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Returns the same list of bodies that was passed in, with each body's ax, ay, az attributes updated in place. |

**Side effects**

- Resets ax, ay, az of every body in the list to zero before computing.
- Mutates ax, ay, az of every body to accumulate pairwise gravitational acceleration contributions.

**References**

- [MIN_DIST](nbody.py.md#variables)
- [G](nbody.py.md#variables)

**Uncertainties**

- Whether G is an attribute of self (e.g. self.G) or a module-level constant.
- Whether MIN_DIST is defined on self or at module scope.
- Exact attribute names for position and mass on the body objects (assumed x/y/z and mass from the summary).
- Whether the displacement components use body.position.x or body.x or some other accessor.

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

---

### step <a id="fn-step-50"></a>

*nbody.py:50-59*

**Developer comment**

> Semi-implicit Euler step: velocities from accelerations, then positions.

**Description**

Advances each body in the simulation by one time step using a semi-implicit (symplectic) Euler integrator: first updates velocities from accelerations, then updates positions from the new velocities.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The integrator/stepper instance (class unknown). |
| `bodies` | An iterable of body objects, each exposing x, y, z, vx, vy, vz, ax, ay, az attributes. |
| `dt` | Time-step size (duration) to apply to the velocity and position updates. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Returns None (no explicit return statement). |

**Side effects**

- Mutates each body's velocity components (vx, vy, vz) by adding acceleration × dt.
- Mutates each body's position components (x, y, z) by adding updated velocity × dt.

**Uncertainties**

- The class that owns this method (self's type) is not visible in the provided snippet.
- The concrete type of the bodies iterable (list, tuple, set, generator) is not stated.
- The units of dt (e.g. seconds, milliseconds) are not specified.
- Whether the two-pass ordering is intentional (symplectic Euler) or incidental cannot be confirmed without broader context.
- Whether bodies is expected to be a fixed-length collection or could be mutated externally during iteration is unclear.

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

---

### total_energy <a id="fn-total_energy-62"></a>

*nbody.py:62-72*

**Developer comment**

> Total mechanical energy: kinetic plus pairwise potential.

**Description**

Computes the total energy of a system of N bodies by summing their individual kinetic energies and subtracting the pairwise gravitational potential energy for every unique pair.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The instance this method is bound to (no state is read or mutated). |
| `bodies` | A sequence of body objects, each exposing .x, .y, .z, .mass, and .kinetic_energy(). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A numeric value representing the total energy: sum of kinetic energies minus the sum of G*mi*mj/d over all unique pairs. |

**References**

- Vec3
- [G](nbody.py.md#variables)
- bodies[i].kinetic_energy
- bodies[i].mass
- bodies[i].x
- bodies[i].y
- bodies[i].z

**Uncertainties**

- The exact type of the bodies sequence (list, tuple, custom iterable) is not visible in this snippet.
- The value and units of the module-level constant G are not shown.
- The implementation of kinetic_energy() on each body is not visible here.

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

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `G` | 7 | number | Numeric constant representing the gravitational constant used in the N-body simulation's force calculations. |
| `MIN_DIST` | 8 | number | A numeric constant that sets a lower bound on inter-body distance, used to prevent singularities (division by zero or extremely small values … |
| `PARAMS` | 10 | table | A module-level parameter table (dictionary) in nbody.py that holds configuration values for the N-body simulation. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
