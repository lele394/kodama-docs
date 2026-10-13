"""Backend registry: manifest discovery, validation, routing, install/remove.

A backend is a self-contained directory inside this package:

    backends/<dir>/
        manifest.toml   # identity, capabilities, requirements
        __init__.py     # a package exposing extract(source, relpath)

The pipeline sees only the stable API of this module, unchanged from the
old flat layout:

    EXTRACTORS              {'.lua': extract, ...}  (ready backends only)
    extract(source, relpath)
    builtins_for(relpath)
    module_candidates(module, relpath)
    UnsupportedLanguage

Backend management (used by the ``main.py`` verbs):

    list_backends()       status of every installed backend
    install_backend(url)  git-clone a backend repo into backends/
    remove_backend(name)  delete one installed backend
    active_backend_ids()  {ext: 'name@version'} — stamped into symbols.json
    backends_compatible(files, stored)

A backend with unmet requirements (missing executable / python package), a
failed import, an unsupported api_version, or an extension claimed by two
backends is *unavailable or conflicted*, not fatal: the other backends keep
working and ``--list-backends`` explains why.

Contract for backend authors: backends/backend_design.md.
"""
import importlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
from importlib.util import find_spec

#: Backend API contract versions this registry understands. A backend whose
#: api_version is not here is refused (see status 'unavailable'), so a newer
#: backend cannot silently produce a shape the pipeline does not know.
SUPPORTED_API_VERSIONS = ('1',)

_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
_SPEC_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*')


class UnsupportedLanguage(Exception):
    """No ready backend claims this file extension."""


def _root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------- discovery + check

def _backend_dirs():
    """(dirname, dirpath, manifest_path) for every subdirectory of this
    package that carries a manifest.toml, sorted by dirname."""
    out = []
    try:
        entries = sorted(os.listdir(_root()))
    except OSError:
        return out
    for e in entries:
        d = os.path.join(_root(), e)
        m = os.path.join(d, 'manifest.toml')
        if (not e.startswith('.') and os.path.isdir(d)
                and os.path.isfile(m)):
            out.append((e, d, m))
    return out


def _new_backend(dirname, dpath, mpath) -> dict:
    return {
        'dir': dirname, 'path': dpath, 'manifest_path': mpath,
        'name': dirname, 'version': '?', 'api_version': '?',
        'description': '', 'source': '',
        'languages': [], 'extensions': [],
        'capabilities': {}, 'requirements': {},
        'status': 'invalid', 'issues': [],
        'module': None, 'extract': None,
    }


def _check_manifest(b: dict) -> None:
    """Fill identity/capabilities from manifest.toml; record issues."""
    try:
        with open(b['manifest_path'], 'rb') as fh:
            raw = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as e:
        b['issues'].append(f'manifest unreadable: {e}')
        return
    if not isinstance(raw, dict):
        b['issues'].append('manifest: top level must be a table')
        return
    meta = raw.get('backend') or {}
    caps = raw.get('capabilities') or {}
    reqs = raw.get('requirements') or {}
    if not isinstance(meta, dict) or not isinstance(caps, dict) \
            or not isinstance(reqs, dict):
        b['issues'].append('manifest: [backend]/[capabilities]/'
                           '[requirements] must be tables')
        return

    name = meta.get('name')
    if not isinstance(name, str) or not _NAME_RE.match(name):
        b['issues'].append('backend.name: required, '
                           '[a-z0-9][a-z0-9_-]* (e.g. "kodama-clang")')
    else:
        b['name'] = name
    version = meta.get('version')
    if not isinstance(version, str) or not version.strip():
        b['issues'].append('backend.version: required (e.g. "0.1.0")')
    else:
        b['version'] = version.strip()
    api = str(meta.get('api_version', '')).strip()
    if not api:
        b['issues'].append('backend.api_version: required (e.g. "1")')
    else:
        b['api_version'] = api
        if api not in SUPPORTED_API_VERSIONS:
            b['issues'].append(
                f'api_version {api!r} not supported here '
                f'(supports {", ".join(SUPPORTED_API_VERSIONS)})')
    desc = meta.get('description')
    if not isinstance(desc, str) or not desc.strip():
        b['issues'].append('backend.description: required')
    else:
        b['description'] = desc.strip()
    b['source'] = meta.get('source') or ''

    langs = caps.get('languages') or []
    if isinstance(langs, list) and all(isinstance(x, str) for x in langs):
        b['languages'] = list(langs)
    else:
        b['issues'].append('capabilities.languages: optional list of strings')

    exts = caps.get('extensions')
    if (isinstance(exts, list) and exts
            and all(isinstance(x, str) and x.startswith('.') for x in exts)):
        b['extensions'] = sorted({x.lower() for x in exts})
    else:
        b['issues'].append('capabilities.extensions: required non-empty '
                           'list of dotted extensions (e.g. [".lua"])')

    caps_out = {}
    for k in ('symbols', 'references', 'call_graph', 'types'):
        v = caps.get(k, False)
        if not isinstance(v, bool):
            b['issues'].append(f'capabilities.{k}: optional boolean')
        else:
            caps_out[k] = v
    b['capabilities'] = caps_out

    reqs_out = {}
    exes = reqs.get('executables') or []
    if isinstance(exes, list) and all(isinstance(x, str) for x in exes):
        reqs_out['executables'] = list(exes)
    else:
        b['issues'].append('requirements.executables: optional list of '
                           'command names (e.g. ["clang"])')
    py = reqs.get('python') or []
    if isinstance(py, list) and all(isinstance(x, str) for x in py):
        reqs_out['python'] = list(py)
    else:
        b['issues'].append('requirements.python: optional list of pip '
                           'specifiers (e.g. ["tree-sitter-lua==0.5.0"])')
    b['requirements'] = reqs_out


def _check_runtime(b: dict) -> None:
    """Import the backend package and check its runtime requirements."""
    try:
        mod = importlib.import_module(f'backends.{b["dir"]}')
    except Exception as e:  # noqa: BLE001 - per-backend isolation by design
        b['issues'].append(f'import failed: {type(e).__name__}: {e}')
        return
    fn = getattr(mod, 'extract', None)
    if not callable(fn):
        b['issues'].append('no callable extract(source, relpath) in package')
        return
    b['module'] = mod
    b['extract'] = fn

    missing_exe = [x for x in b['requirements'].get('executables', [])
                   if shutil.which(x) is None]
    if missing_exe:
        b['issues'].append('missing executable(s): ' +
                           ', '.join(missing_exe))

    missing_py = [spec for spec in b['requirements'].get('python', [])
                  if not _spec_importable(spec)]
    if missing_py:
        b['issues'].append('missing python package(s): ' +
                           ', '.join(missing_py))

    if b['issues']:
        b['status'] = 'unavailable'


def _spec_name(spec: str) -> str:
    m = _SPEC_NAME_RE.match(spec.strip())
    return m.group(0) if m else spec.strip()


def _spec_importable(spec: str) -> bool:
    """True when the python package named by a pip specifier is importable.
    Distribution names use dashes; module names use underscores
    (PEP 503 normalization)."""
    try:
        return find_spec(_spec_name(spec).replace('-', '_')) is not None
    except (ImportError, ValueError):
        return False


def _apply_conflicts(backends) -> None:
    """Two backends may not share a name, and two may not claim an
    extension: ambiguous routing is a conflict for both, never a shadow."""
    by_name = {}
    by_ext = {}
    for b in backends:
        by_name.setdefault(b['name'], []).append(b)
        for e in b['extensions']:
            by_ext.setdefault(e, []).append(b)
    for b in backends:
        if b['status'] != 'ready':
            continue
        oth = [x['name'] for x in by_name[b['name']] if x is not b]
        if oth:
            b['status'] = 'conflict'
            b['issues'].append(f'name also claimed by {", ".join(oth)}')
        for e in b['extensions']:
            oth = [x['name'] for x in by_ext[e] if x is not b]
            if oth:
                b['status'] = 'conflict'
                b['issues'].append(
                    f'extension {e} also claimed by {", ".join(oth)}')


def _registry() -> list:
    """Load every installed backend with status + issues. Fresh each call:
    install/remove changes the directory, so there is no cache to invalidate."""
    out = []
    for dirname, dpath, mpath in _backend_dirs():
        b = _new_backend(dirname, dpath, mpath)
        _check_manifest(b)
        if not b['issues']:
            b['status'] = 'ready'
            _check_runtime(b)
        out.append(b)
    _apply_conflicts(out)
    return out


def _routing() -> dict:
    """{ext: backend} for ready backends only."""
    return {e: b for b in _registry()
            if b['status'] == 'ready' for e in b['extensions']}


def _ext(relpath: str) -> str:
    return os.path.splitext(relpath)[1].lower()


# ------------------------------------------------------------- stable API

#: Extension -> extract() dispatch table (ready backends only). ``main``
#: filters the scan on ``set(EXTRACTORS)``; a new manifest is live as soon
#: as its directory exists and its requirements are met.
EXTRACTORS = {e: b['extract'] for e, b in _routing().items()}


def extract(source: str, relpath: str) -> dict:
    """Route one file to the ready backend that claims its extension."""
    routing = _routing()
    b = routing.get(_ext(relpath))
    if b is None:
        raise UnsupportedLanguage(
            f'no ready backend claims {_ext(relpath)!r} '
            f'(see --list-backends)')
    return b['extract'](source, relpath)


def builtins_for(relpath: str) -> set:
    """Names the backend treats as builtin/stdlib (not cross-file links)."""
    b = _routing().get(_ext(relpath))
    if b is None or b['module'] is None:
        return set()
    names = getattr(b['module'], 'BUILTIN_NAMES', None)
    return set(names) if names is not None else set()


def _generic_module_candidates(module: str, ext: str) -> list:
    out = [f'{module}{ext}', f'{module}/init{ext}']
    slashed = module.replace('.', '/')
    if slashed != module:
        out += [f'{slashed}{ext}', f'{slashed}/init{ext}']
    return out


def module_candidates(module: str, relpath: str) -> list:
    """Relpath candidates a language import of ``module`` could resolve to.
    Backend-provided when available; otherwise a generic file/package guess
    from the backend's extension."""
    b = _routing().get(_ext(relpath))
    if b is not None and b['module'] is not None:
        fn = getattr(b['module'], 'module_candidates', None)
        if callable(fn):
            return fn(module, relpath)
    return _generic_module_candidates(module, _ext(relpath))


# ------------------------------------------------------- cache stamping

def active_backend_ids() -> dict:
    """{ext: 'name@version'} for every ready backend. Stamped into
    symbols.json so a replaced/upgraded backend invalidates the cache."""
    return {e: f"{b['name']}@{b['version']}"
            for b in _registry() if b['status'] == 'ready'
            for e in b['extensions']}


def backends_compatible(files, stored) -> bool:
    """True when every scanned file's extension was extracted by the same
    backend name@version recorded in a previous analysis (symbols.json).
    ``stored`` is the stamp from that file; None means 'unknown' (pre-stamp
    format) → re-extract once."""
    if not isinstance(stored, dict):
        return False
    now = active_backend_ids()
    for f in files:
        ext = _ext(f['relpath'])
        if stored.get(ext) != now.get(ext):
            return False
    return True


# ----------------------------------------------------- list / install / rm

def list_backends() -> list:
    """One entry per installed backend, stable order (by directory)."""
    return _registry()


def install_backend(url: str) -> dict:
    """Install a backend: git-clone ``url`` into ``backends/<name>/``,
    then check its manifest and requirements (pip-installing any missing
    python packages with the current interpreter).

    Security: this runs third-party code at import time — only install
    backends you have reviewed. Returns {'url', 'dir', 'steps': [(ok, msg)]}.
    """
    if shutil.which('git') is None:
        raise SystemExit('install: git not found on PATH')
    base = url.rstrip('/').split('/')[-1]
    if base.endswith('.git'):
        base = base[:-4]
    # the directory is also a python package (backends.<base>), so keep it
    # a valid identifier: lowercase, [a-z0-9_]
    base = re.sub(r'[^a-z0-9_]', '_', base.lower()).strip('_')
    if not base:
        raise SystemExit('install: cannot derive a directory name from '
                         f'the URL {url!r}')
    dest = os.path.join(_root(), base)
    if os.path.exists(dest):
        raise SystemExit(f'install: backends/{base} already exists '
                         '(--remove it first)')

    r = subprocess.run(['git', 'clone', '--depth', '1', url, dest],
                       capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        detail = (r.stderr or r.stdout or '').strip()
        raise SystemExit(f'install: git clone failed:\n{detail}')
    steps = [(True, f'cloned {url} -> backends/{base}/')]

    b = next((x for x in _registry() if x['dir'] == base), None)
    if b is None or b['status'] == 'invalid':
        steps.append((False, 'installed directory has no valid manifest.toml'))
        return {'url': url, 'dir': base, 'steps': steps}

    missing = [spec for spec in b['requirements'].get('python', [])
               if not _spec_importable(spec)]
    if missing:
        r = subprocess.run([sys.executable, '-m', 'pip', 'install',
                            '--disable-pip-version-check', *missing],
                           capture_output=True, text=True)
        if r.returncode == 0:
            steps.append((True, 'installed python dependencies: '
                                + ', '.join(missing)))
        else:
            steps.append((False, 'pip install failed for: '
                                 + ', '.join(missing)))

    b = next((x for x in _registry() if x['dir'] == base), None)
    if b['status'] == 'ready':
        steps.append((True, f"backend '{b['name']}' is now ready"))
    else:
        steps.append((False, f"backend '{b['name']}' is {b['status']}: "
                             + '; '.join(b['issues'])))
    return {'url': url, 'dir': base, 'steps': steps}


def remove_backend(name: str) -> str:
    """Delete one installed backend, matched by manifest name (or
    directory name). Returns the directory name removed."""
    root = os.path.realpath(_root())
    for dirname, dpath, mpath in _backend_dirs():
        mname = None
        try:
            with open(mpath, 'rb') as fh:
                mname = (tomllib.load(fh).get('backend') or {}).get('name')
        except (OSError, tomllib.TOMLDecodeError):
            pass
        if mname != name and dirname != name:
            continue
        # defense in depth: only ever delete a real dir inside backends/
        if not os.path.realpath(dpath).startswith(root + os.sep):
            raise SystemExit('remove: refusing to delete a path outside '
                             'the backends package')
        shutil.rmtree(dpath)
        return dirname
    available = ', '.join(b['name'] for b in _registry()) or 'none'
    raise SystemExit(f"remove: no backend named {name!r} "
                     f'(installed: {available})')


__all__ = [
    'EXTRACTORS', 'UnsupportedLanguage',
    'extract', 'builtins_for', 'module_candidates',
    'list_backends', 'install_backend', 'remove_backend',
    'active_backend_ids', 'backends_compatible',
    'SUPPORTED_API_VERSIONS',
]
