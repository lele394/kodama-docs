# vec3.py

## Summary

The file defines a Vec3 class representing a 3D vector with float x, y, z components and provides standard vector arithmetic operations including addition, subtraction, scalar multiplication, dot product, length, and normalization. It also declares module-level constants EPS and ZERO, and a tag() function that returns a type identifier string. The class implements __repr__ for readable string output of vector values.
**Main purpose:** To provide a lightweight 3D vector type with the essential arithmetic and geometric operations needed for physics computations.
**Role in project:** It serves as a foundational math utility module within the N-body simulation project, supplying the vector type and operations used to represent positions, velocities, and forces.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [tag](#fn-tag-8) | 8 |  | Returns the module-level constant TAG, which likely identifies the file or module for debugging or logging purposes. |
| [__init__](#fn-__init__-15) | 15 | self, x, y, z | Constructor for a 3D vector object that stores three scalar components (x, y, z), each coerced to a float. All three components default to 0 … |
| [add](#fn-add-21) | 21 | self, other | Performs component-wise addition of two 3D vectors and returns a new Vec3 instance representing the sum. |
| [sub](#fn-sub-25) | 25 | self, other | Performs component-wise subtraction of another Vec3 from this instance, returning a new Vec3 whose x, y, and z components are the difference … |
| [scale](#fn-scale-29) | 29 | self, s | Returns a new Vec3 whose x, y, and z components are each multiplied by the scalar s, effectively producing a scaled copy of the vector. |
| [dot](#fn-dot-33) | 33 | self, other | Computes the scalar dot product of this 3D vector with another vector by summing the products of corresponding x, y, and z components. |
| [length](#fn-length-37) | 37 | self | Computes the Euclidean norm (magnitude) of the vector by taking the square root of the dot product with itself. Returns the result clamped t … |
| [normalize](#fn-normalize-45) | 45 | self | Returns a normalized (unit-length) copy of the vector by dividing it by its own magnitude. If the vector's length is at or below a small eps … |
| [__repr__](#fn-__repr__-51) | 51 | self | Returns a human-readable string representation of the Vec3 instance, formatted as 'Vec3(x, y, z)' showing its three components. |

### tag <a id="fn-tag-8"></a>

*vec3.py:8-9*

**Description**

Returns the module-level constant TAG, which likely identifies the file or module for debugging or logging purposes.

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The value of the module-level constant TAG. |

**References**

- [TAG](vec3.py.md#variables)

**Uncertainties**

- The actual value and type of TAG are not visible in the provided source.
- The intended purpose of TAG (e.g., logging identifier, version string, debug marker) is not stated in the code.

```py
def tag():
    return TAG
```

---

### __init__ <a id="fn-__init__-15"></a>

*vec3.py:15-18*

**Description**

Constructor for a 3D vector object that stores three scalar components (x, y, z), each coerced to a float. All three components default to 0.0.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance being initialized. |
| `x` | X component of the vector (default 0.0). Coerced to float. |
| `y` | Y component of the vector (default 0.0). Coerced to float. |
| `z` | Z component of the vector (default 0.0). Coerced to float. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | Sets self.x, self.y, and self.z as float attributes on the instance. Returns None (implicit). |

**Side effects**

- Mutates the instance by setting .x, .y, and .z attributes to float values.

**References**

- float

```py
def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
```

---

### add <a id="fn-add-21"></a>

*vec3.py:21-22*

**Developer comment**

> Component-wise sum of two vectors.

**Description**

Performs component-wise addition of two 3D vectors and returns a new Vec3 instance representing the sum.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The current Vec3 instance whose components are added. |
| `other` | A Vec3 instance whose x, y, and z components are added to self. |

**Outputs**

| Name | Description |
| --- | --- |
| `Vec3` | A new Vec3 whose x, y, z components are the sums of the corresponding components of self and other. |

**References**

- Vec3

```py
def add(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)
```

---

### sub <a id="fn-sub-25"></a>

*vec3.py:25-26*

**Developer comment**

> Component-wise difference a - b.

**Description**

Performs component-wise subtraction of another Vec3 from this instance, returning a new Vec3 whose x, y, and z components are the differences of the corresponding components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance from which components are subtracted. |
| `other` | The Vec3 instance whose components are subtracted from self. |

**Outputs**

| Name | Description |
| --- | --- |
| `return` | A new Vec3 with components (self.x - other.x, self.y - other.y, self.z - other.z). |

**References**

- Vec3

**Uncertainties**

- Whether 'other' is type-checked or expected to be a Vec3 specifically, or if any object with x, y, z attributes would work.

```py
def sub(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)
```

---

### scale <a id="fn-scale-29"></a>

*vec3.py:29-30*

**Developer comment**

> Scale by a scalar.

**Description**

Returns a new Vec3 whose x, y, and z components are each multiplied by the scalar s, effectively producing a scaled copy of the vector.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance providing the original x, y, z components. |
| `s` | Scalar factor to multiply each component by. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A new Vec3 instance with components (self.x*s, self.y*s, self.z*s). |

**References**

- Vec3

```py
def scale(self, s):
        return Vec3(self.x * s, self.y * s, self.z * s)
```

**Call graph**

- [vec3.py](vec3.py.md)
  - [normalize:49](vec3.py.md#fn-normalize-45)

---

### dot <a id="fn-dot-33"></a>

*vec3.py:33-34*

**Developer comment**

> Dot product of two vectors.

**Description**

Computes the scalar dot product of this 3D vector with another vector by summing the products of corresponding x, y, and z components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance providing the first vector's x, y, z components. |
| `other` | Another vector-like object with x, y, z attributes to dot with self. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A scalar numeric value equal to self.x*other.x + self.y*other.y + self.z*other.z. |

**Uncertainties**

- The exact class of 'other' is not annotated; it is assumed to be a Vec3 or Vec3-like object.
- The class name (e.g. Vec3) is not visible in the provided snippet.
- Whether x, y, z are plain floats or numpy/scipy types is not specified.

```py
def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z
```

**Call graph**

- [vec3.py](vec3.py.md)
  - [length:38](vec3.py.md#fn-length-37)

---

### length <a id="fn-length-37"></a>

*vec3.py:37-39*

**Developer comment**

> Euclidean length, guarded against sub-epsilon results.

**Description**

Computes the Euclidean norm (magnitude) of the vector by taking the square root of the dot product with itself. Returns the result clamped to a minimum value of EPS to guard against zero-length vectors.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance whose length is computed. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A float representing the vector's magnitude, guaranteed to be at least EPS. |

**References**

- self.dot
- [EPS](vec3.py.md#variables)

**Uncertainties**

- The numeric value of EPS is not visible in this snippet; it is presumably a module-level constant defined elsewhere in vec3.py.
- Whether `dot` performs any additional side effects (e.g., validation) cannot be confirmed from this code alone.

```py
def length(self):
        d = (self.dot(self)) ** 0.5
        return d if d >= EPS else EPS
```

**Call graph**

- [vec3.py](vec3.py.md)
  - [normalize:46](vec3.py.md#fn-normalize-45)

---

### normalize <a id="fn-normalize-45"></a>

*vec3.py:45-49*

**Developer comment**

> Unit vector in this direction; the zero vector maps to ZERO.

**Description**

Returns a normalized (unit-length) copy of the vector by dividing it by its own magnitude. If the vector's length is at or below a small epsilon threshold, a zero vector is returned instead to avoid division by zero.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The vec3 instance to normalize. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A unit-length vec3 (self scaled by 1/length), or the ZERO constant if the vector's length is <= EPS. |

**References**

- [EPS](vec3.py.md#variables)
- [ZERO](vec3.py.md#variables)
- vec3.length
- vec3.scale

**Uncertainties**

- Whether self.scale() mutates self in place or returns a new vector; the code treats the result as a return value but the internal implementation is not visible.
- The exact value of EPS (module-level constant, not shown in this snippet).
- The exact representation of ZERO (likely a vec3(0,0,0) constant, but not confirmed).

```py
def normalize(self):
        d = self.length()
        if d <= EPS:
            return ZERO
        return self.scale(1.0 / d)
```

---

### __repr__ <a id="fn-__repr__-51"></a>

*vec3.py:51-52*

**Description**

Returns a human-readable string representation of the Vec3 instance, formatted as 'Vec3(x, y, z)' showing its three components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance whose components are displayed. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A string in the form 'Vec3({x}, {y}, {z})' where x, y, z are the attribute values of the instance. |

**References**

- Vec3.x
- Vec3.y
- Vec3.z

```py
def __repr__(self):
        return f"Vec3({self.x}, {self.y}, {self.z})"
```

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `EPS` | 3 | number | A numeric constant (EPS) defined in vec3.py, typically used as a small floating-point tolerance for near-equality comparisons on vector comp … |
| `ZERO` | 4 | table | A module-level constant in the 3D vector (vec3) module representing the zero vector, initialized as a table (likely a tuple or list of three … |
| `TAG` | 5 | string | A string constant defined in vec3.py, likely used as a tag or label identifier for the module or its logging output within the N-body simula … |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
