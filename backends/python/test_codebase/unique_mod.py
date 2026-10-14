"""The single definition of a name used unbound elsewhere (inferred target)."""
import probe


@probe.traced
def do_the_thing(x):
    return x * 6
