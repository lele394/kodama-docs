"""Source of a re-exported function."""
import probe


@probe.traced
def public_fn(x):
    return x + 100
