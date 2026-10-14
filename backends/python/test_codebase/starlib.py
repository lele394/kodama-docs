"""Provides a star-exported function (the caller uses `from starlib import *`)."""
__all__ = ['star_fn']

import probe


@probe.traced
def star_fn(x):
    return x * 3
