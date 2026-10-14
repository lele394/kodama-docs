"""Case-sensitive import binding: `Value` (case_mod) and `value` (case2_mod)
are distinct symbols; the analyzer must not confuse them by case."""
from case_mod import Value
from case2_mod import value


def run():
    a = Value(1)
    b = value(1)
    return a + b
