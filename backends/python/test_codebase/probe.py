"""Runtime provenance probe for the Python test fixture.

`traced` wraps a function so that every call it receives is recorded with
three pieces of runtime ground truth:

  * ``callee`` — the function's name;
  * ``origin`` — ``{file, line, name}`` where the function is DEFINED
    (``func.__file__`` + ``func.__code__.co_firstlineno``);
  * ``site``   — ``{file, line}`` where it was CALLED (the caller frame).

This is the runtime truth that the static graph must reproduce: a correct
analyzer must place a CALLS edge at ``site`` pointing to the function at
``origin``. The probe uses only the standard library (``inspect``/``os``)
and contains no fixture-specific logic, so it stays a neutral oracle.
"""
import inspect
import os

#: The fixture root (the directory this file lives in). All reported paths
#: are made relative to it, matching the graph's ``relpath`` convention.
ROOT = os.path.dirname(os.path.abspath(__file__))

#: Recorded calls, in execution order (cleared by :func:`reset`).
CALLS = []


def _rel(path):
    """``path`` made relative to the fixture root, or ``None``."""
    if not path:
        return None
    try:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:
        return None
    return rel.replace(os.sep, '/')


def _caller_frame():
    """The frame that invoked the traced function (i.e. the wrapper's caller).

    ``currentframe()`` is this helper, ``.f_back`` is the probe wrapper, and
    the wrapper's ``.f_back`` is the real caller — whose ``f_lineno`` is the
    call site we want to record."""
    try:
        caller = inspect.currentframe().f_back.f_back
        return caller
    except Exception:  # pragma: no cover - defensive
        return None


def _def_line(func):
    """The 1-based line of the function's ``def`` (skipping decorators).

    CPython reports ``co_firstlineno`` (and ``inspect.getsourcelines``) at the
    *first decorator* for a decorated function, but the analyzer's node is the
    ``def`` line. Walk the source to the ``def`` keyword so truth and graph
    agree."""
    try:
        src, start = inspect.getsourcelines(func)
    except (OSError, TypeError, SyntaxError):  # pragma: no cover - defensive
        return func.__code__.co_firstlineno
    for i, line in enumerate(src):
        if line.lstrip().startswith('def ') or line.lstrip().startswith('async def '):
            return start + i
    return func.__code__.co_firstlineno


def traced(func):
    """Decorator: record every call to ``func`` with its origin + site."""
    origin_file = _rel(func.__code__.co_filename)
    origin_line = _def_line(func)

    def wrapper(*args, **kwargs):
        caller = _caller_frame()
        site_file = None
        site_line = None
        if caller is not None:
            site_file = _rel(getattr(caller, 'f_globals', {}).get('__file__'))
            site_line = getattr(caller, 'f_lineno', None)
        CALLS.append({
            'callee': func.__name__,
            'origin': {'file': origin_file, 'line': origin_line,
                       'name': func.__name__},
            'site': {'file': site_file, 'line': site_line},
        })
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__qualname__ = func.__qualname__
    wrapper.__wrapped__ = func
    wrapper.__origin_file__ = origin_file
    wrapper.__origin_line__ = origin_line
    return wrapper


def resolve(obj):
    """Runtime origin ``{file, line, name}`` of a class/constant object."""
    try:
        file = inspect.getsourcefile(obj) or getattr(obj, '__file__', None)
        _, start = inspect.getsourcelines(obj)
    except (OSError, TypeError):
        return {'file': None, 'line': 0,
                'name': getattr(obj, '__name__', str(obj))}
    return {'file': _rel(file), 'line': start,
            'name': getattr(obj, '__name__', str(obj))}


def reset():
    CALLS.clear()
