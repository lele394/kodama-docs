-- nbody.lua — pairwise gravitational N-body integrator (softened).

local vec3 = require("vec3")

local G = 6.674e-11
local MIN_DIST = 1e-9

local NBody = {}

NBody.params = {
  dt = 1 / 60,
  iterations = 2,
  softening = 1e-4,
}

--- Accumulates the pairwise gravitational acceleration of every body.
--- Uses a softened distance to avoid singularities at close range.
function NBody:accelerations(bodies)
  local n = #bodies
  for i = 1, n do
    bodies[i].ax = 0
    bodies[i].ay = 0
    bodies[i].az = 0
  end

  for i = 1, n - 1 do
    for j = i + 1, n do
      local dx = bodies[j].x - bodies[i].x
      local dy = bodies[j].y - bodies[i].y
      local dz = bodies[j].z - bodies[i].z
      local d2 = dx * dx + dy * dy + dz * dz
      if d2 < MIN_DIST then
        d2 = MIN_DIST
      end
      local dist = math.sqrt(d2)
      local inv3 = 1.0 / (dist * d2)
      local fi = G * bodies[j].mass * inv3
      local fj = G * bodies[i].mass * inv3
      bodies[i].ax = bodies[i].ax + fi * dx
      bodies[i].ay = bodies[i].ay + fi * dy
      bodies[i].az = bodies[i].az + fi * dz
      bodies[j].ax = bodies[j].ax - fj * dx
      bodies[j].ay = bodies[j].ay - fj * dy
      bodies[j].az = bodies[j].az - fj * dz
    end
  end

  return bodies
end

-- Semi-implicit Euler step: velocities from accelerations, then positions.
function NBody:step(bodies, dt)
  for i = 1, #bodies do
    local b = bodies[i]
    b.vx = b.vx + b.ax * dt
    b.vy = b.vy + b.ay * dt
    b.vz = b.vz + b.az * dt
  end

  for i = 1, #bodies do
    local b = bodies[i]
    b.x = b.x + b.vx * dt
    b.y = b.y + b.vy * dt
    b.z = b.z + b.vz * dt
  end
end

-- Total mechanical energy: kinetic plus pairwise potential.
function NBody:total_energy(bodies)
  local e = 0
  for i = 1, #bodies do
    e = e + bodies[i]:kinetic_energy()
  end

  for i = 1, #bodies - 1 do
    for j = i + 1, #bodies do
      local d = vec3.length(vec3.sub(
        { bodies[j].x, bodies[j].y, bodies[j].z },
        { bodies[i].x, bodies[i].y, bodies[i].z }))
      e = e - G * bodies[i].mass * bodies[j].mass / d
    end
  end

  return e
end

return NBody
