"""Unbound call to a name defined in exactly one project module: it may be
inferred, but only labeled as inferred (never presented as verified)."""


def trap():
    return do_the_thing(5)   # expect: inferred unique_mod.py::do_the_thing
