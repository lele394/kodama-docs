"""Uses the PROJECT `random` module (shadowing the stdlib one)."""
import random

SEED_VALUE = random.seed(7)


def run():
    return random.randint(0, 9)
