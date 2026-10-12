-- main.lua — entry point: builds a body system and runs a fixed number of steps.

local NBody = require("physics.nbody")
local Body = require("physics.body")
local log = require("log")

local FPS = 60
local RUNS = 300
local MODE = "circular"

-- Build n bodies on a circular orbit around a central mass of 1000.
local function make_circular_system(n)
  local bodies = { Body:new(0, 0, 0, 0, 0, 0, 1000) }
  for i = 1, n do
    local r = 10 + i * 2
    local v = math.sqrt(1000 / r)
    local a = 2 * math.pi * i / n
    table.insert(bodies, Body:new(
      math.cos(a) * r, math.sin(a) * r, 0,
      -math.sin(a) * v, math.cos(a) * v, 0, 1))
  end
  return bodies
end

-- Build n bodies at pseudo-random positions with small random velocities.
local function make_random_system(n, seed)
  math.randomseed(seed)
  local bodies = {}
  for i = 1, n do
    table.insert(bodies, Body:new(
      math.random() * 20 - 10, math.random() * 20 - 10, math.random() * 20 - 10,
      math.random() * 0.2 - 0.1, math.random() * 0.2 - 0.1, 0,
      1 + math.random()))
  end
  return bodies
end

-- Advance one frame: compute total energy, then integrate the bodies.
local function tick(sim, bodies, dt)
  local e = sim:total_energy(bodies)
  sim:accelerations(bodies)
  sim:step(bodies, dt)
  log.info("energy=" .. tostring(e))
end

local function main()
  local bodies
  if MODE == "circular" then
    bodies = make_circular_system(8)
  else
    bodies = make_random_system(12, os.time())
  end

  local dt = 1 / FPS
  for _ = 1, RUNS do
    tick(NBody, bodies, dt)
  end

  return #bodies
end

return main
