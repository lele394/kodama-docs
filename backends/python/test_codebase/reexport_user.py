"""Imports `public_fn` via the re-export module; the real definition lives
in realmod2.py, so a correct resolver infers it there (not the re-exporter)."""
from reexport import public_fn


def run():
    return public_fn(1)
