"""Circular import pair (with circ_b). Each calls the other; the chain is
bounded by the `x < 2` guard so it terminates at runtime. Module-level
`import` (not `from ... import`) keeps the circular import importable."""
import probe
import circ_b


@probe.traced
def from_a(x):
    return circ_b.from_b(x + 1) if x < 2 else x


def run():
    return from_a(0)
