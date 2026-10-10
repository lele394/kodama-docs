"""Per-language source extraction backends.

Parsing is offloaded to tree-sitter; each backend module only walks the
concrete syntax tree and projects it into doc_maker's per-file symbol shape:

    {'functions': [...], 'file_vars': [...], 'calls': [...], 'imports': [...]}

The rest of the pipeline (graph, LLM prose, markdown) is language-agnostic
and sees only that shape. To add a language: drop a module here with an
``extract(source, relpath)`` function and register its file extension.
"""
import os


class UnsupportedLanguage(Exception):
    pass


def _register_lua():
    from backends.lua import extract
    return extract


def _register_python():
    from backends.python import extract
    return extract


EXTRACTORS = {
    '.lua': _register_lua(),
    '.py': _register_python(),
}

__all__ = ['EXTRACTORS', 'UnsupportedLanguage', 'extract',
           'builtins_for', 'module_candidates']


def _ext(relpath: str) -> str:
    return os.path.splitext(relpath)[1].lower()


def builtins_for(relpath: str) -> set:
    """Names a language treats as builtin/stdlib (not cross-file links)."""
    ext = _ext(relpath)
    if ext == '.lua':
        from backends.lua import BUILTIN_NAMES
    elif ext == '.py':
        from backends.python import BUILTIN_NAMES
    else:
        return set()
    return set(BUILTIN_NAMES)


def module_candidates(module: str, relpath: str) -> list:
    """Relpath candidates a language import of ``module`` could resolve to."""
    ext = _ext(relpath)
    if ext == '.py':
        return [module + '.py', module + '/__init__.py',
                module.replace('.', '/') + '.py',
                module.replace('.', '/') + '/__init__.py']
    return [module + '.lua', module + '/init.lua',
            module.replace('.', '/') + '.lua',
            module.replace('.', '/') + '/init.lua']


def extract(source: str, relpath: str) -> dict:
    fn = EXTRACTORS.get(_ext(relpath))
    if fn is None:
        raise UnsupportedLanguage(f'no extractor registered for {_ext(relpath)!r}')
    return fn(source, relpath)
