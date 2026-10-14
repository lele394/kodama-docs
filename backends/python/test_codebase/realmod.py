"""The real target module. `decoy.py` defines an identically named
function with a different result to trip up name-only matchers."""
import probe


@probe.traced
def compute(x):
    return x * 2
