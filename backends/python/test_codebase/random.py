"""A project module named like the stdlib `random`. A project import
binding must win over the builtin/stdlib assumption for these calls."""
import probe


@probe.traced
def seed(n):
    return n


@probe.traced
def randint(a, b):
    return a + b
