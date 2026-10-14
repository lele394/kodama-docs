"""Function-meta, vararg, and default-argument-call cases that were previously
unguarded. Each behavior below is pinned by the harness's function-meta /
file-vars / call checks against the runtime + AST oracle, so a regression in
any of them re-fails the self-test loudly:

* ``splat(*args, **kwargs)``  -> params report both, vararg=True
* ``sized(size=1024*1024, sep='*')`` -> the ``*`` in a default is NOT a vararg
* ``Widget.norm``             -> method qualified name, and the class attribute
                                 ``TIMEOUT`` must NOT leak out as a file_var
* ``MODULE_VAR``              -> a real module-level file_var
* ``norm(scale=make_default())`` -> a resolvable call site in a default arg
"""
import probe
from metalib import make_default

# module-level variable: MUST be extracted as a file_var
MODULE_VAR = 7


class Widget:
    # class attribute: must NOT leak out as a module file_var
    TIMEOUT = 30

    def norm(self, scale=make_default()):
        # default-arg expression is a resolvable call site (metalib::make_default)
        return scale * 2


def splat(*args, **kwargs):
    # varargs must be reported as params and vararg=True
    return (args, kwargs)


def sized(size=1024 * 1024, sep='*'):
    # a ``*`` inside a default expression must NOT be misread as a vararg
    return (size, sep)


# developer comment glued above the def line (must become developer_comment)
def plain_glued():
    return 'plain'


# developer comment glued above the FIRST decorator line (decorated-definition
# anchor: the extractor must still attach it, not lose it behind the decorator)
@probe.traced
def deco_glued():
    return 'deco'


def run():
    # exercise the vararg functions (untraced, but present for extraction)
    w = Widget()
    return (w.norm(), splat(1, 2, x=3), sized())
