"""Defines `value` (lowercase v) — a different name than case_mod.Value."""
import probe


@probe.traced
def value(x):
    return x * 5
