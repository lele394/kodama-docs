"""Redefined function: the LATER definition is the one that is live at
runtime, so `compute` must link to the second `old_impl`, not the first."""
import probe


def old_impl(x):
    return 0


@probe.traced
def compute(x):
    return old_impl(x) + 1


def old_impl(x):
    return x * 2


def run():
    return compute(3)
