"""Lib module providing a traced function for the default-argument call case.

``make_default`` is ``probe.traced`` so that calling it inside a *default
argument expression* is recorded as runtime ground truth (a call site with a
resolvable origin), pinning the fix that default/annotation call sites are
extracted rather than dropped.
"""
import probe


@probe.traced
def make_default():
    return 42
