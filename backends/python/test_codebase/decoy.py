"""DECOY: same function names as realmod.py, different results. A resolver
that picks by name alone (rather than the import binding) gets this one."""
import probe


@probe.traced
def compute(x):
    return x * 999
