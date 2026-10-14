"""Calls that resolve to the stdlib/builtin (not project) definitions."""
import collections
import math
import os


def run():
    a = math.sqrt(9)
    b = os.path.join('a', 'b')
    c = len(collections.OrderedDict())
    d = zip([1], [2])
    return a, b, c, d
