"""Circular import pair (with circ_a)."""
import probe
import circ_a


@probe.traced
def from_b(x):
    return circ_a.from_a(x + 1) if x < 2 else x


def run():
    return from_b(0)
