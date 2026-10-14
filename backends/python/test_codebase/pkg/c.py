"""pkg.c: `from .b import helper` (level-1, explicit symbol)."""
from .b import helper
import probe


@probe.traced
def run():
    return helper(2)
