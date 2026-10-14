"""Star import: `star_fn` is not an explicit binding, so resolving it is a
documented inference (status: inferred), not a verified resolution."""
from starlib import *


def run():
    return star_fn(1)
