"""Per-language source extraction backends.

Parsing is offloaded to tree-sitter; each backend module only walks the
concrete syntax tree and projects it into doc_maker's per-file symbol shape:

    {'functions': [...], 'file_vars': [...], 'calls': [...], 'imports': [...]}

Each function record carries ``developer_comment``: the text of the comment
block glued directly above the function, or None. The rest of the pipeline
(graph, LLM prose, markdown) is language-agnostic and sees only that shape.

Full contract: see backends/backend_design.md. To add a language: drop a
module here with an ``extract(source, relpath)`` function and register its
file extension.
"""
import os


class UnsupportedLanguage(Exception):
    pass


def _all_comments(root, types=('comment',)):
    """Comment nodes of ``root`` in document order."""
    out = []

    def w(n):
        if n.type in types:
            out.append(n)
        else:
            for c in n.children:
                w(c)

    w(root)
    return out


def _dev_comment(comments, fn_line, clean):
    """Text of the comment block glued directly above 1-based line
    ``fn_line``, or None.

    The block is the maximal run of comments whose last line sits exactly
    on the line immediately above the function (and above each other);
    any other content or a blank line between comment and function breaks
    the glue. ``clean`` maps one comment node to its cleaned text.
    """
    run = []
    top = fn_line
    while True:
        hit = next((c for c in comments if c.end_point[0] + 1 == top - 1),
                   None)
        if hit is None:
            break
        run.insert(0, hit)
        top = hit.start_point[0] + 1
    if not run:
        return None
    text = '\n'.join(clean(c) for c in run).strip()
    return text or None


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
