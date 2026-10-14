"""pkg.b: provides `helper` used by pkg.a and pkg.c via relative imports."""
import probe


@probe.traced
def helper(x):
    return x * 10
