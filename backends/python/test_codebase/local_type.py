"""A local function named like the builtin `type()`."""
import probe


@probe.traced
def type(x):
    return x + 1


def run():
    return type(1)
