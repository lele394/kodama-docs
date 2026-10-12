# vec3.py

## Summary

vec3.py defines a lightweight Vec3 class representing a 3D vector with x, y, and z floating-point components. It provides standard vector arithmetic operations including addition, subtraction, scalar multiplication, dot product, length calculation, and normalization. The module also defines file-level constants (EPS, ZERO, TAG) and a tag() helper function for identifying vector instances.
**Main purpose:** To supply a basic 3D vector type with common mathematical operations used throughout the simulation.
**Role in project:** Serves as a low-level utility module that provides the Vec3 data type and arithmetic primitives consumed by other parts of the N-body simulation.

## Functions

| Function | Line | Parameters | Description |
| --- | --- | --- | --- |
| [tag](#fn-tag-8) | 8 |  | Returns the module-level constant TAG defined in vec3.py. |
| [__init__](#fn-__init__-15) | 15 | self, x, y, z | Constructor for a 3D vector class that initializes the x, y, and z components from the provided arguments, converting each to a float. |
| [add](#fn-add-21) | 21 | self, other | Performs component-wise addition of two 3D vectors and returns a new Vec3 instance representing the sum. |
| [sub](#fn-sub-25) | 25 | self, other | Subtracts the components of another vector from this Vec3 and returns a new Vec3 containing the component-wise differences. |
| [scale](#fn-scale-29) | 29 | self, s | Creates and returns a new Vec3 instance whose x, y, and z components are each multiplied by the scalar s. The original Vec3 is not modified. |
| [dot](#fn-dot-33) | 33 | self, other | Computes the dot product of two 3D vectors by summing the products of their corresponding x, y, and z components. |
| [length](#fn-length-37) | 37 | self | Computes the Euclidean length (magnitude) of the vector by taking the square root of its dot product with itself, returning at least the con … |
| [normalize](#fn-normalize-45) | 45 | self | Normalizes the vector by scaling it to unit length. If the vector's length is at or below the EPS threshold, returns a zero vector instead o … |
| [__repr__](#fn-__repr__-51) | 51 | self | Returns a human-readable string representation of the Vec3 instance, formatted as 'Vec3(x, y, z)' using the instance's coordinate attributes … |

### tag <a id="fn-tag-8"></a>

*vec3.py:8-9*

**Description**

Returns the module-level constant TAG defined in vec3.py.

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | The value of the module-level constant TAG. |

**References**

- [TAG](vec3.py.md#variables)

**Uncertainties**

- The value or type of TAG is not visible in this snippet; it is defined elsewhere in vec3.py.

```py
def tag():
    return TAG
```

---

### __init__ <a id="fn-__init__-15"></a>

*vec3.py:15-18*

**Description**

Constructor for a 3D vector class that initializes the x, y, and z components from the provided arguments, converting each to a float.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | Instance reference. |
| `x` | X component of the vector (default 0.0). |
| `y` | Y component of the vector (default 0.0). |
| `z` | Z component of the vector (default 0.0). |

**Side effects**

- Sets self.x to float(x).
- Sets self.y to float(y).
- Sets self.z to float(z).

**Uncertainties**

- The class name is not visible in the provided snippet; inferred to be a 3D vector class from the filename vec3.py.

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
| `self` | The Vec3 instance whose components (x, y, z) are the left operand of the addition. |
| `other` | Another object with x, y, z attributes representing the right operand of the addition. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A new Vec3 instance whose x, y, z components are the element-wise sums of self and other. |

**References**

- Vec3

**Uncertainties**

- The exact type or class of the `other` parameter is not declared; only its x, y, z attributes are used.

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

Subtracts the components of another vector from this Vec3 and returns a new Vec3 containing the component-wise differences.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance whose components are the left operand. |
| `other` | A Vec3 (or compatible object) whose components are subtracted component-wise. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A new Vec3 instance with x = self.x - other.x, y = self.y - other.y, z = self.z - other.z. |

**References**

- Vec3

**Uncertainties**

- Whether `other` is strictly typed as Vec3 or could be any object with x, y, z attributes.

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

Creates and returns a new Vec3 instance whose x, y, and z components are each multiplied by the scalar s. The original Vec3 is not modified.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance to scale. |
| `s` | Scalar value to multiply each component by. |

**Outputs**

| Name | Description |
| --- | --- |
| `Vec3` | A new Vec3 with components (x*s, y*s, z*s). |

**References**

- Vec3

**Uncertainties**

- The type of s is not annotated; it could be int, float, or another numeric type.

```py
def scale(self, s):
        return Vec3(self.x * s, self.y * s, self.z * s)
```

---

### dot <a id="fn-dot-33"></a>

*vec3.py:33-34*

**Developer comment**

> Dot product of two vectors.

**Description**

Computes the dot product of two 3D vectors by summing the products of their corresponding x, y, and z components.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The vector instance on which the method is called; provides x, y, z components. |
| `other` | Another vector-like object with x, y, z components to take the dot product with. |

**Outputs**

| Name | Description |
| --- | --- |
| `return` | A scalar numeric value equal to self.x * other.x + self.y * other.y + self.z * other.z. |

**Uncertainties**

- The exact numeric type of the return value depends on the types of the x, y, z components (int vs float).
- The type of 'other' is not enforced; any object with x, y, z attributes would work.

```py
def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z
```

---

### length <a id="fn-length-37"></a>

*vec3.py:37-39*

**Developer comment**

> Euclidean length, guarded against sub-epsilon results.

**Description**

Computes the Euclidean length (magnitude) of the vector by taking the square root of its dot product with itself, returning at least the constant EPS to prevent a zero result.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The vector instance whose magnitude is being computed. |

**Outputs**

| Name | Description |
| --- | --- |
| `return` | A float representing the vector's length, clamped to a minimum of EPS. |

**References**

- self.dot
- [EPS](vec3.py.md#variables)

**Uncertainties**

- The numeric value of EPS is defined elsewhere (likely a module-level constant in vec3.py).
- The exact class name is not visible in the provided snippet, though the file name suggests a Vec3 type.

```py
def length(self):
        d = (self.dot(self)) ** 0.5
        return d if d >= EPS else EPS
```

---

### normalize <a id="fn-normalize-45"></a>

*vec3.py:45-49*

**Developer comment**

> Unit vector in this direction; the zero vector maps to ZERO.

**Description**

Normalizes the vector by scaling it to unit length. If the vector's length is at or below the EPS threshold, returns a zero vector instead of performing the division to avoid division by near-zero.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The vector instance to normalize. |

**Outputs**

| Name | Description |
| --- | --- |
| `return value` | A zero vector (ZERO) if the length is <= EPS, otherwise a new vector scaled to unit length. |

**References**

- [EPS](vec3.py.md#variables)
- [ZERO](vec3.py.md#variables)
- self.length()
- self.scale()

**Uncertainties**

- The exact numeric value of the EPS constant.
- Whether ZERO is a shared singleton or constructed per access.
- Whether self.scale() returns a new vector or mutates in place and returns self.

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

Returns a human-readable string representation of the Vec3 instance, formatted as 'Vec3(x, y, z)' using the instance's coordinate attributes.

**Parameters**

| Name | Description |
| --- | --- |
| `self` | The Vec3 instance whose coordinates are formatted into the string. |

**Outputs**

| Name | Description |
| --- | --- |
| `return` | A string of the form 'Vec3(x, y, z)' containing the values of the instance's x, y, and z attributes. |

**References**

- Vec3.x
- Vec3.y
- Vec3.z

**Uncertainties**

- Whether x, y, z are plain numbers or nested objects; their string formatting depends on their own __str__ or __repr__.

```py
def __repr__(self):
        return f"Vec3({self.x}, {self.y}, {self.z})"
```

## File-level variables <a id="variables"></a>

| Variable | Line | Init | Description |
| --- | --- | --- | --- |
| `EPS` | 3 | number | A numeric constant (likely a small floating-point epsilon threshold) defined in the vec3 module for use in numerical comparisons or toleranc … |
| `ZERO` | 4 | table | A zero vector constant in the vec3 module, representing a 3D vector with all components set to zero, used as a neutral or default value in v … |
| `TAG` | 5 | string | A string constant assigned in vec3.py, likely used as a short tag or label for logging or debugging output within the vector3 module. |

---
_Generated by kodama-docs. Prose produced by an LLM; structure and links generated deterministically._
