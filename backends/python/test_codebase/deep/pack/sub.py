"""Sibling module in deep/pack."""
import probe


@probe.traced
def fire(n):
    return n * 13
