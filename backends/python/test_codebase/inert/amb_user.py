"""Ambiguous binding: the name `greet` is defined in TWO project modules.
The tool must NOT guess one — no edge, and both candidates must be visible.
(inert: the two `from ... import greet` cannot both be imported cleanly.)"""
from amb_a import greet
from amb_b import greet


def ask():
    return greet('x')   # expect: ambiguous
