"""Defines `Value` (capital V)."""
import probe


@probe.traced
def Value(x):
    return x * 4
