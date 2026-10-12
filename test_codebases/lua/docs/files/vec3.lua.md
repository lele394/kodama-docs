# vec3.lua

## Summary

vec3.lua is a small Lua module that implements 3D vector (vec3) operations, exposing six functions on a table V: add, sub, scale, dot, length, and normalize. Vectors are represented as 3-element arrays, and the module includes an epsilon constant (EPS) and a zero vector (ZERO) to guard against division-by-zero in length and normalize. It also defines a TAG constant, likely used for type identification.
**Main purpose:** To provide a lightweight 3D vector math library with basic arithmetic and geometric operations for use in the N-body simulation.
**Role in project:** A low-level math utility module within the N-body simulation project, supplying the vector operations that physics and rendering code rely on to manipulate position, velocity, and force vectors.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [V.add](#fn-add-10) | 10 | a, b | Performs component-wise addition of two 3D vectors and returns a new vector table containing the summed components. |
| [V.sub](#fn-sub-15) | 15 | a, b | Performs element-wise subtraction of vector b from vector a and returns the result as a new 3-component table. |
| [V.scale](#fn-scale-20) | 20 | v, s | Creates and returns a new 3D vector whose components are the elements of the input vector v each multiplied by the scalar s. It does not mod … |
| [V.dot](#fn-dot-25) | 25 | a, b | Computes the dot (scalar) product of two 3-component vectors. Returns the sum of the element-wise products of the corresponding components. |
| [V.length](#fn-length-30) | 30 | v | Computes the Euclidean length (magnitude) of a vector by taking the square root of its dot product with itself, clamping the result to a min … |
| [V.normalize](#fn-normalize-42) | 42 | v | Normalizes a 3D vector to unit length by dividing it by its magnitude. Returns the ZERO vector if the input length is at or below EPS to avo … |

### V.add <a id="fn-add-10"></a>

*vec3.lua:10-12*

**Developer comment**

> Component-wise sum of two vectors.

**Description**

Performs component-wise addition of two 3D vectors and returns a new vector table containing the summed components.

**Parameters**

| Name | Description |
| --- | --- |
| `a` | First 3-component vector (array-like table with indices 1, 2, 3). |
| `b` | Second 3-component vector (array-like table with indices 1, 2, 3). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A new 3-element table where element i is a[i] + b[i]. |

**References**

- [V](vec3.lua.md)

**Uncertainties**

- The exact Lua type or metatable of the input vectors beyond being indexable at keys 1, 2, 3 is not specified.

```lua
function V.add(a, b)
  return { a[1] + b[1], a[2] + b[2], a[3] + b[3] }
end
```

---

### V.sub <a id="fn-sub-15"></a>

*vec3.lua:15-17*

**Developer comment**

> Component-wise difference a - b.

**Description**

Performs element-wise subtraction of vector b from vector a and returns the result as a new 3-component table.

**Parameters**

| Name | Description |
| --- | --- |
| `a` | First 3-component vector (table) to subtract from. |
| `b` | Second 3-component vector (table) to subtract. |

**Outputs**

| Name | Description |
| --- | --- |
| `result` | A new 3-element table containing {a[1]-b[1], a[2]-b[2], a[3]-b[3]}. |

**Uncertainties**

- The structure of the V table (its other methods) is not visible in this snippet.
- Whether a and b are guaranteed to be 3-component vectors is not enforced in the code.

```lua
function V.sub(a, b)
  return { a[1] - b[1], a[2] - b[2], a[3] - b[3] }
end
```

**Call graph**

- [nbody.lua](nbody.lua.md)
  - [NBody.total_energy:77](nbody.lua.md#fn-total_energy-69)

---

### V.scale <a id="fn-scale-20"></a>

*vec3.lua:20-22*

**Developer comment**

> Scale a vector by a scalar.

**Description**

Creates and returns a new 3D vector whose components are the elements of the input vector v each multiplied by the scalar s. It does not modify the original vector.

**Parameters**

| Name | Description |
| --- | --- |
| `v` | A 3-element array (vec3) representing the vector to scale. |
| `s` | A numeric scalar factor to multiply each component of v by. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A new 3-element array with components { v[1]*s, v[2]*s, v[3]*s }. |

**References**

- [V.normalize](vec3.lua.md#fn-normalize-42)

**Uncertainties**

- Whether V is a module table defined elsewhere in the project.
- Whether v is guaranteed to have exactly 3 elements or could have a 4th (w) component in some contexts.

```lua
function V.scale(v, s)
  return { v[1] * s, v[2] * s, v[3] * s }
end
```

**Call graph**

- [vec3.lua](vec3.lua.md)
  - [V.normalize:47](vec3.lua.md#fn-normalize-42)

---

### V.dot <a id="fn-dot-25"></a>

*vec3.lua:25-27*

**Developer comment**

> Dot product of two vectors.

**Description**

Computes the dot (scalar) product of two 3-component vectors. Returns the sum of the element-wise products of the corresponding components.

**Parameters**

| Name | Description |
| --- | --- |
| `a` | First 3-component vector (array with indices 1, 2, 3). |
| `b` | Second 3-component vector (array with indices 1, 2, 3). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A scalar number equal to a[1]*b[1] + a[2]*b[2] + a[3]*b[3]. |

**References**

- [V](vec3.lua.md)
- [V.length](vec3.lua.md#fn-length-30)

```lua
function V.dot(a, b)
  return a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
end
```

**Call graph**

- [vec3.lua](vec3.lua.md)
  - [V.length:31](vec3.lua.md#fn-length-30)

---

### V.length <a id="fn-length-30"></a>

*vec3.lua:30-36*

**Developer comment**

> Euclidean length, guarded against sub-epsilon results.

**Description**

Computes the Euclidean length (magnitude) of a vector by taking the square root of its dot product with itself, clamping the result to a minimum of EPS to avoid degenerate values.

**Parameters**

| Name | Description |
| --- | --- |
| `v` | The vector whose length is to be computed. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The Euclidean length of the vector as a number, clamped to at least EPS. |

**References**

- [V.dot](vec3.lua.md#fn-dot-25)
- math.sqrt
- [EPS](vec3.lua.md#variables)

**Uncertainties**

- The value of EPS is not visible in this snippet.
- The exact shape/layout of v (number of components) is implied by the filename vec3.lua but not stated in the code.

```lua
function V.length(v)
  local d = math.sqrt(V.dot(v, v))
  if d < EPS then
    return EPS
  end
  return d
end
```

**Call graph**

- [nbody.lua](nbody.lua.md)
  - [NBody.total_energy:77](nbody.lua.md#fn-total_energy-69)
- [vec3.lua](vec3.lua.md)
  - [V.normalize:43](vec3.lua.md#fn-normalize-42)

---

### V.normalize <a id="fn-normalize-42"></a>

*vec3.lua:42-48*

**Developer comment**

> Unit vector in the direction of v; the zero vector maps to ZERO.

**Description**

Normalizes a 3D vector to unit length by dividing it by its magnitude. Returns the ZERO vector if the input length is at or below EPS to avoid division by a near-zero value.

**Parameters**

| Name | Description |
| --- | --- |
| `v` | The vector (vec3) to normalize. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A unit-length vector (V.scale of v by 1/d), or ZERO if the vector length is <= EPS. |

**References**

- [V.length](vec3.lua.md#fn-length-30)
- [V.scale](vec3.lua.md#fn-scale-20)
- [EPS](vec3.lua.md#variables)
- [ZERO](vec3.lua.md#variables)

**Uncertainties**

- The exact value of EPS (module-level constant, not shown).
- The exact value/type of ZERO (module-level constant, not shown).
- Whether V.length and V.scale handle edge cases like nil or non-vector inputs.

```lua
function V.normalize(v)
  local d = V.length(v)
  if d <= EPS then
    return ZERO
  end
  return V.scale(v, 1 / d)
end
```

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `V` | 3 | table | A table that serves as the module/namespace for 3D vector operations in the vec3 module, providing vector utility functions used by the N-bo … |
| `EPS` | 5 | number | A numeric epsilon (tolerance) constant used within the vec3 module, typically for floating-point comparisons such as checking if a component … |
| `ZERO` | 6 | table | A constant representing the zero vector in 3D space, stored as a Lua table (e.g. {0,0,0}) within the vec3 utility module. |
| `TAG` | 7 | string | A string constant used as a module or log identifier for the vec3 module, typically prepended to debug or log messages. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
