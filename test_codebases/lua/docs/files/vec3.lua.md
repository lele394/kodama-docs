# vec3.lua

## Summary

vec3.lua is a small Lua module that implements basic 3D vector operations (add, subtract, scale, dot product, length, and normalize) using 3-element arrays as the vector representation. It defines an epsilon constant (EPS) and a zero vector (ZERO) to guard against division-by-zero in the length and normalize functions. The module exposes these functions under a single table V, providing a lightweight vector-math utility for the project.
**Main purpose:** Provide a set of fundamental 3D vector arithmetic and magnitude operations for use by other parts of the simulation.
**Role in project:** Serves as the foundational vector-math utility module that other modules in the N-body simulation demo rely on for position, velocity, and force computations.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [V.add](#fn-add-10) | 10 | a, b | Performs element-wise addition of two 3-component vectors and returns a new vector table containing the summed components. |
| [V.sub](#fn-sub-15) | 15 | a, b | Performs component-wise subtraction of two 3-component vectors, returning a new table where each element is the difference of the correspond … |
| [V.scale](#fn-scale-20) | 20 | v, s | Scales a 3D vector by a scalar value, returning a new vector table with each component multiplied by the scalar. |
| [V.dot](#fn-dot-25) | 25 | a, b | Computes the dot product of two 3-dimensional vectors represented as Lua arrays with indices 1 through 3. |
| [V.length](#fn-length-30) | 30 | v | Computes the Euclidean length (magnitude) of a 3D vector by taking the square root of its dot product with itself. If the result is below a  … |
| [V.normalize](#fn-normalize-42) | 42 | v | Normalizes a 3D vector to unit length by dividing it by its magnitude, returning a predefined ZERO vector if the input magnitude is at or be … |

### V.add <a id="fn-add-10"></a>

*vec3.lua:10-12*

**Developer comment**

> Component-wise sum of two vectors.

**Description**

Performs element-wise addition of two 3-component vectors and returns a new vector table containing the summed components.

**Parameters**

| Name | Description |
| --- | --- |
| `a` | First 3-component vector (indexed table with elements 1, 2, 3). |
| `b` | Second 3-component vector (indexed table with elements 1, 2, 3). |

**Outputs**

| Name | Description |
| --- | --- |
| `return` | A new 3-element table where each element is the sum of the corresponding elements of a and b. |

**References**

- [V](vec3.lua.md)

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

Performs component-wise subtraction of two 3-component vectors, returning a new table where each element is the difference of the corresponding components.

**Parameters**

| Name | Description |
| --- | --- |
| `a` | The first 3-component vector (table) to be subtracted from. |
| `b` | The second 3-component vector (table) to subtract from a. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A new 3-element table {a[1]-b[1], a[2]-b[2], a[3]-b[3]} representing the component-wise difference. |

**References**

- [V](vec3.lua.md)

**Uncertainties**

- Input vectors are assumed to be 3-element tables, but no type checking or validation is performed in the code.
- The function is named V.sub, implying it belongs to a V (vector) module/namespace, but the module context is not visible in the snippet.

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

Scales a 3D vector by a scalar value, returning a new vector table with each component multiplied by the scalar.

**Parameters**

| Name | Description |
| --- | --- |
| `v` | A 3-element table representing a 3D vector (v[1], v[2], v[3]). |
| `s` | Scalar multiplier applied to each component of the vector. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A new 3-element table where each component is the corresponding component of v multiplied by s. |

**References**

- [V](vec3.lua.md)
- [V.normalize](vec3.lua.md#fn-normalize-42)

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

Computes the dot product of two 3-dimensional vectors represented as Lua arrays with indices 1 through 3.

**Parameters**

| Name | Description |
| --- | --- |
| `a` | First 3D vector (array with elements at indices 1, 2, 3). |
| `b` | Second 3D vector (array with elements at indices 1, 2, 3). |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The scalar dot product: a[1]*b[1] + a[2]*b[2] + a[3]*b[3]. |

**References**

- [V](vec3.lua.md)

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

Computes the Euclidean length (magnitude) of a 3D vector by taking the square root of its dot product with itself. If the result is below a small threshold EPS, it returns EPS instead to avoid zero-length values.

**Parameters**

| Name | Description |
| --- | --- |
| `v` | A 3D vector whose magnitude is to be computed. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The Euclidean length of v, clamped to a minimum of EPS. |

**References**

- [V.dot](vec3.lua.md#fn-dot-25)
- [EPS](vec3.lua.md#variables)
- math.sqrt

**Uncertainties**

- The value and type of EPS are not defined in this snippet.
- The exact field layout of v (e.g., .x/.y/.z vs .1/.2/.3) is not visible here; it is implied by V.dot's implementation.

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

Normalizes a 3D vector to unit length by dividing it by its magnitude, returning a predefined ZERO vector if the input magnitude is at or below an epsilon threshold to avoid division by near-zero.

**Parameters**

| Name | Description |
| --- | --- |
| `v` | The 3D vector to normalize. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A unit-length vector (result of scaling v by 1/length), or ZERO if the vector's length is <= EPS. |

**References**

- [V.length](vec3.lua.md#fn-length-30)
- [V.scale](vec3.lua.md#fn-scale-20)
- [EPS](vec3.lua.md#variables)
- [ZERO](vec3.lua.md#variables)

**Uncertainties**

- The exact value of EPS is not visible in this snippet.
- The exact definition of ZERO (likely a zero vector {0,0,0}) is not shown here.
- Whether V.scale mutates its input vector in place or returns a new vector is not visible in this snippet.

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
| `V` | 3 | table | A table defined in vec3.lua, most likely representing a 3D vector (x, y, z components) or a namespace of vector3 helper functions for the N- … |
| `EPS` | 5 | number | A small numeric epsilon constant defined in vec3.lua, typically used as a threshold for floating-point near-zero comparisons in vector opera … |
| `ZERO` | 6 | table | A constant table representing the zero vector (origin) in 3D space, used as a default or identity value for vector operations in the vec3 mo … |
| `TAG` | 7 | string | A string constant that serves as an identifier tag for the vec3 vector module, commonly used to label log messages or debug output with the  … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
