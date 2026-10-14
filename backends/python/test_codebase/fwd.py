"""A forward reference: the call textually precedes the definition."""
import probe


def run():
    return late_fn(1)


@probe.traced
def late_fn(x):
    return x + 1
