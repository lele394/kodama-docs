"""pkg.sub.leaf: `from .. import b` (level-2 relative -> pkg.b)."""
from .. import b
import probe


@probe.traced
def run():
    return b.helper(7)
