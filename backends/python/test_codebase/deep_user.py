"""Imports deep modules by dotted path and calls them; these resolve by
unique-name inference (no explicit binding to the deep module)."""
import deep.pack.mod
import deep.pack


def run():
    a = deep.pack.mod.launch(3)
    b = deep.pack.sub.fire(1)
    return a + b
