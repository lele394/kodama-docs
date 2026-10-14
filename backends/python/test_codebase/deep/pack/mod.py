"""A module nested two directories deep."""
import probe


@probe.traced
def launch(n):
    return n * 11
