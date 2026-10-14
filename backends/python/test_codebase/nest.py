"""Closure scoping: inside `outer`, the nested `inner` shadows the
module-level `inner`; outside it, the module-level one is live. A
scope-aware resolver must send each call to the right definition."""
import probe

MARK = []


@probe.traced
def outer(x):
    @probe.traced
    def inner(x):
        MARK.append('nested')
        return x + 1
    return inner(x)


@probe.traced
def inner(x):
    MARK.append('top')
    return x + 2


def top_use(x):
    return inner(x)


def run():
    return outer(1), top_use(1)
