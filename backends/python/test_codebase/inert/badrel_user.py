"""A relative import whose target does not exist must be VISIBLE as an
unresolved import (the current code discards relative imports entirely).
The call on its binding is external. (inert: `from . import` would raise.)"""
from . import nosuch_sib    # expect: import-unresolved


def trap():
    return nosuch_sib.poke(1)   # expect: external nosuch_sib.poke
