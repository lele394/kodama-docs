"""vec3 — minimal 3D vector helpers for the nbody simulation."""

EPS = 1e-6
ZERO = (0.0, 0.0, 0.0)
TAG = "vec3"


def tag():
    return TAG


class Vec3:
    """Plain 3D vector with component accessors x, y, z."""

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    # Component-wise sum of two vectors.
    def add(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    # Component-wise difference a - b.
    def sub(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    # Scale by a scalar.
    def scale(self, s):
        return Vec3(self.x * s, self.y * s, self.z * s)

    # Dot product of two vectors.
    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    # Euclidean length, guarded against sub-epsilon results.
    def length(self):
        d = (self.dot(self)) ** 0.5
        return d if d >= EPS else EPS

    # This comment is separated from the method below by a blank line,
    # so the extractor must not glue it to the method.

    # Unit vector in this direction; the zero vector maps to ZERO.
    def normalize(self):
        d = self.length()
        if d <= EPS:
            return ZERO
        return self.scale(1.0 / d)

    def __repr__(self):
        return f"Vec3({self.x}, {self.y}, {self.z})"
