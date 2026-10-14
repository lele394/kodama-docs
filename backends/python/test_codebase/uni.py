"""A non-ASCII function name: resolution is name-exact, unicode included."""
import probe


@probe.traced
def begrüße(x):
    return 'hallo ' + x


def run():
    return begrüße('x')
