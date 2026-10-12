"""body — a single simulated body with position, velocity and mass."""

G = 6.674e-11
SOFTENING = 1e-4


class Body:
    """A point mass in the simulation with mutable kinematic state."""

    def __init__(self, x, y, z, vx, vy, vz, mass):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.mass = mass
        self.ax, self.ay, self.az = 0.0, 0.0, 0.0

    # Reset the body state, keeping the same instance.
    def reset(self, x, y, z, vx, vy, vz):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.ax, self.ay, self.az = 0.0, 0.0, 0.0

    # Apply a force over dt as an impulse: F*dt = m*dv.
    def apply_force(self, fx, fy, fz, dt):
        self.vx += fx * dt / self.mass
        self.vy += fy * dt / self.mass
        self.vz += fz * dt / self.mass

    # Translational kinetic energy: 0.5*m*v^2.
    def kinetic_energy(self):
        v2 = self.vx * self.vx + self.vy * self.vy + self.vz * self.vz
        return 0.5 * self.mass * v2
