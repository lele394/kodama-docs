"""Fakes inside a docstring must not become symbols.

def fake_in_docstring():
    return 1
"""
# def fake_in_comment():
#     return 2


def real(x):
    return 'real:' + str(x)


def run():
    return real(1)
