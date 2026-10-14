"""An aliased import: `compute as compute2` still binds to decoy.compute."""
from decoy import compute as compute2


def run():
    return compute2(4)
