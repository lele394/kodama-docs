"""Calls with no possible target in this codebase: each must be VISIBLE as
external (orange), never silently dropped. (inert: never executed.)"""


def trap(car):
    mystery_engine(42)     # expect: external mystery_engine
    logger.warn('x')       # expect: external logger.warn
    car.accelerate(1)      # expect: external car.accelerate
    return None
