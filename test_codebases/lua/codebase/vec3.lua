-- vec3.lua — minimal 3D vector helpers for the nbody simulation.

local V = {}

local EPS = 1e-6
local ZERO = { 0, 0, 0 }
local TAG = "vec3"

-- Component-wise sum of two vectors.
function V.add(a, b)
  return { a[1] + b[1], a[2] + b[2], a[3] + b[3] }
end

-- Component-wise difference a - b.
function V.sub(a, b)
  return { a[1] - b[1], a[2] - b[2], a[3] - b[3] }
end

-- Scale a vector by a scalar.
function V.scale(v, s)
  return { v[1] * s, v[2] * s, v[3] * s }
end

-- Dot product of two vectors.
function V.dot(a, b)
  return a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
end

-- Euclidean length, guarded against sub-epsilon results.
function V.length(v)
  local d = math.sqrt(V.dot(v, v))
  if d < EPS then
    return EPS
  end
  return d
end

-- This comment is separated from the function below by a blank line,
-- so the extractor must not glue it to the function.

-- Unit vector in the direction of v; the zero vector maps to ZERO.
function V.normalize(v)
  local d = V.length(v)
  if d <= EPS then
    return ZERO
  end
  return V.scale(v, 1 / d)
end

return V
