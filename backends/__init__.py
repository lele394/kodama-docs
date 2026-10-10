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


EXTRACTORS = {
    '.lua': _register_lua(),
}

__all__ = ['EXTRACTORS', 'UnsupportedLanguage', 'extract']


def extract(source: str, relpath: str) -> dict:
    ext = os.path.splitext(relpath)[1].lower()
    fn = EXTRACTORS.get(ext)
    if fn is None:
        raise UnsupportedLanguage(f'no extractor registered for {ext!r}')
    return fn(source, relpath)
