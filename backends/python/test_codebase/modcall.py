"""Two modules on one import line; both are used via `module.function`."""
import realmod, decoy


def run():
    a = realmod.compute(5)
    b = decoy.compute(6)
    return a - b
