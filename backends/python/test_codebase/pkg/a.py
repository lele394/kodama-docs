"""pkg.a: `from . import b` (level-1 relative) then calls b.helper."""
from . import b
import probe


@probe.traced
def run():
    return b.helper(1)
