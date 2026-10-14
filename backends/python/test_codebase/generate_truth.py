"""Generate the runtime ground truth for the Python test fixture (JSON to stdout).

This is the "self-reporting" half of the fixture: it imports every
*executable* module (in a fixed order) with the fixture root on ``sys.path``,
calls each module's ``run()`` (if present), and emits two lists of runtime
facts that a correct static analyzer must reproduce:

* ``calls`` — one entry per distinct call site:
      ``{site: {file, line}, callee, origin: {file, line, name}}``
  ``origin`` is where the callee is DEFINED (runtime truth); ``site`` is
  where it was called. Inert trap modules are never imported, so only
  resolvable call sites appear here.

* ``imports`` — one entry per top-level import statement of an imported
  module, resolved against the importing module's live namespace:
      ``{file, line, bound, module_file}``
  ``module_file`` is the fixture-relative path of the imported module when it
  lives inside the fixture, else ``null`` (stdlib — which the graph reports as
  an unresolved import by design).

Only the standard library is used (``sys``, ``ast``, ``inspect``, ``json``,
``importlib``). No LLM, no network. The inert ``inert/`` directory is never
imported, so its deliberately-broken imports never raise.
"""
import ast
import importlib
import inspect
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Executable core only — the inert/ traps are deliberately NOT imported.
MODULES = [
    # libs first (define the traced functions the callers invoke)
    'realmod', 'decoy', 'random', 'starlib', 'realmod2', 'reexport',
    'case_mod', 'case2_mod', 'unique_mod', 'utils',
    'pkg.b', 'pkg.a', 'pkg.c', 'pkg.sub.leaf',
    'deep.pack.mod', 'deep.pack.sub',
    # then the callers (their run() fires the traced functions)
    'consumer', 'alias_user', 'modcall', 'shadow_user',
    'local_shadow', 'local_type', 'redef', 'nest', 'fwd',
    'circ_a', 'circ_b', 'star_user', 'reexport_user', 'deep_user',
    'std_user', 'sup', 'uni', 'case_user', 'entry',
    'crlf', 'bom',
]


def _rel(path):
    if not path:
        return None
    try:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:
        return None
    if rel.startswith('..') or os.path.isabs(rel):
        return None
    return rel.replace(os.sep, '/')


def _import_names(importer_mod, node):
    """``[(bound, abs_module), ...]`` for every name in an import statement.

    ``abs_module`` is the *absolute* module path the statement imports (what a
    correct resolver should target). Relative imports are resolved against the
    importer's ``__package__``; a bare ``from . import x`` names a submodule.
    ``*`` is kept so star imports are counted (a resolver that drops them will
    simply fail to produce a matching edge)."""
    pkg = (importer_mod.__package__ or '').strip('.')
    parts = [p for p in pkg.split('.') if p]
    out = []
    if isinstance(node, ast.Import):
        for a in node.names:
            out.append((a.asname or a.name.split('.')[0], a.name))
    elif isinstance(node, ast.ImportFrom):
        base_parts = parts[:]
        if node.level:  # climb (level - 1) packages up for `..`, `...`, ...
            for _ in range(node.level - 1):
                if base_parts:
                    base_parts = base_parts[:-1]
        base = '.'.join(base_parts)
        if node.module:
            abs_mod = (base + '.' + node.module) if base else node.module
            for a in node.names:
                out.append((a.asname or a.name, abs_mod))
        else:
            for a in node.names:
                abs_mod = (base + '.' + a.name) if base else a.name
                out.append((a.name, abs_mod))
    return out


def _import_records(importer_mod):
    """``(file, line, bound, abs_module)`` for each imported name."""
    f = _rel(getattr(importer_mod, '__file__', None))
    if f is None:
        return []
    try:
        src = inspect.getsource(importer_mod)
        tree = ast.parse(src)
    except (OSError, SyntaxError, ValueError):
        return []
    recs = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for bound, abs_mod in _import_names(importer_mod, node):
                recs.append((f, node.lineno, bound, abs_mod))
    return recs


def _mod_file(abs_mod):
    """Fixture-relative file of module ``abs_mod`` (or ``None`` for stdlib)."""
    if not abs_mod:
        return None
    m = sys.modules.get(abs_mod)
    if m is None:
        return None
    f = getattr(m, '__file__', None)
    if f:
        return _rel(f)
    for p in (getattr(m, '__path__', None) or []):  # namespace package
        init = os.path.join(p, '__init__.py')
        if os.path.exists(init):
            return _rel(init)
    return None


def _zero_arg(fn):
    """True if ``fn`` can be called with no arguments."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    for p in sig.parameters.values():
        if p.default is inspect.Parameter.empty and \
                p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD,
                          p.VAR_POSITIONAL):
            return False
    return True


def main():
    import probe  # local fixture oracle (now on sys.path)

    import inspect as _insp

    probe.reset()
    imported = []
    for m in MODULES:
        mod = importlib.import_module(m)
        imported.append(mod)
        run = getattr(mod, 'run', None)
        if callable(run) and _zero_arg(run):
            run()

    # drop the generator's own ``run()`` invocations (the harness, not a
    # fixture call site) and dedup identical (site, origin) pairs — the
    # circular pair records the same hop repeatedly.
    self_file = _rel(__file__)
    seen = set()
    calls = []
    for c in probe.CALLS:
        sf = c['site']['file']
        if not sf or sf == self_file:
            continue
        key = (sf, c['site']['line'], c['callee'],
               c['origin']['file'], c['origin']['line'])
        if key in seen:
            continue
        seen.add(key)
        calls.append(c)
    calls.sort(key=lambda c: (c['site']['file'] or '', c['site']['line']))

    # imports: resolve each imported name to its absolute module file
    imports = []
    for mod in imported:
        for (f, line, bound, abs_mod) in _import_records(mod):
            imports.append({'file': f, 'line': line, 'bound': bound,
                            'module_file': _mod_file(abs_mod)})

    json.dump({'calls': calls, 'imports': imports},
              sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
