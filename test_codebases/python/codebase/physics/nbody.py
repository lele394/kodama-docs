"""nbody — pairwise gravitational N-body integrator (softened)."""

import math

from physics.vec3 import Vec3

G = 6.674e-11
MIN_DIST = 1e-9

PARAMS = {
    "dt": 1 / 60,
    "iterations": 2,
    "softening": 1e-4,
}


class NBody:
    """Collection of bodies advanced by pairwise Newtonian gravity."""

    # Accumulates the pairwise gravitational acceleration of every body.
    # Uses a softened distance to avoid singularities at close range.
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

    # Semi-implicit Euler step: velocities from accelerations, then positions.
    def step(self, bodies, dt):
        for b in bodies:
            b.vx += b.ax * dt
            b.vy += b.ay * dt
            b.vz += b.az * dt

        for b in bodies:
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.z += b.vz * dt

    # Total mechanical energy: kinetic plus pairwise potential.
    def total_energy(self, bodies):
        e = sum(b.kinetic_energy() for b in bodies)

        n = len(bodies)
        for i in range(n - 1):
            for j in range(i + 1, n):
                bi, bj = bodies[i], bodies[j]
                d = Vec3(bj.x - bi.x, bj.y - bi.y, bj.z - bi.z).length()
                e -= G * bi.mass * bj.mass / d

        return e
