"""Python import resolution candidates."""


def module_candidates(module, relpath):
    """File paths a Python import of ``module`` could resolve to.

    Python packages use ``__init__.py`` (double underscore), so both the
    plain ``<path>.py`` and the ``<path>/__init__.py`` forms are offered —
    unlike the generic helper, which emits ``init.py`` and would never match
    a package root. (A relative import arrives here already resolved to a
    slashed path by the extractor.)
    """
    slashed = module.replace('.', '/')
    return [f'{slashed}.py', f'{slashed}/__init__.py']
