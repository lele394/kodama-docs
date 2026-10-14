"""Local definitions shadowing builtin names: the same-file local must win
over the builtin assumption for calls in this module."""
import probe


@probe.traced
def print(x):
    return 'printed:' + str(x)


@probe.traced
def zip(a, b):
    return len(a) + len(b)


class list:
    def __init__(self, seq):
        self.seq = seq


def run():
    return print('hi'), zip([1], [2]), list([1, 2])
