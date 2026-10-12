-- body.lua — a single simulated body with position, velocity and mass.

local G = 6.674e-11
local SOFTENING = 1e-4

local Body = {}

-- Create a body at (x,y,z) with velocity (vx,vy,vz) and the given mass.
function Body:new(x, y, z, vx, vy, vz, mass)
  local self = setmetatable({}, { __index = Body })
  self.x, self.y, self.z = x, y, z
  self.vx, self.vy, self.vz = vx, vy, vz
  self.mass = mass
  self.ax, self.ay, self.az = 0, 0, 0
  return self
end

-- Reset the body state, keeping the same table instance.
function Body:reset(x, y, z, vx, vy, vz)
  self.x, self.y, self.z = x, y, z
  self.vx, self.vy, self.vz = vx, vy, vz
  self.ax, self.ay, self.az = 0, 0, 0
end

-- Apply a force over dt as an impulse: F*dt = m*dv.
function Body:apply_force(fx, fy, fz, dt)
  self.vx = self.vx + fx * dt / self.mass
  self.vy = self.vy + fy * dt / self.mass
  self.vz = self.vz + fz * dt / self.mass
end

-- Translational kinetic energy: 0.5*m*v^2.
function Body:kinetic_energy()
  return 0.5 * self.mass * (self.vx * self.vx
                            + self.vy * self.vy
                            + self.vz * self.vz)
end

return Body
