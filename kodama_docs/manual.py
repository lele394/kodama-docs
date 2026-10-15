"""Manual documentation: a user-supplied folder of human-written docs.

``settings.yaml -> project.manual_doc`` points at a folder. Its contents are
copied into ``<output_dir>/manual/`` at render time (the target is pruned and
re-copied each run, so it is always fresh and never stale), and the web server
serves every page exactly like a generated one (``GET /manual/<page>.md``).

Markdown files (``.md``, ``.markdown``, ...) become **section 0**: the first
section of ``index.md`` and the first top-level group in the web sidebar. All
other files are copied verbatim as static assets, so relative links and images
inside the manual docs keep working.

Pure translation — no LLM. Manual pages are prose, not code: they never enter
``symbols.json`` / ``graph.json`` and get no generated summaries.
"""
import json
import os
import shutil

from kodama_docs.util import log

MANUAL_DIRNAME = 'manual'
MD_EXTENSIONS = ('.md', '.markdown', '.mdown', '.mkd')


def _abspath(p):
    return os.path.normpath(os.path.abspath(p))


def _nested(a, b):
    """True if ``a == b`` or one path contains the other."""
    a, b = _abspath(a), _abspath(b)
    return (a == b or a.startswith(b + os.sep)
            or b.startswith(a + os.sep))


def is_markdown(relpath) -> bool:
    return os.path.splitext(str(relpath))[1].lower() in MD_EXTENSIONS


def _title_of(path, fallback):
    """First ``# `` heading in the file, else ``fallback``."""
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            for line in fh:
                if line.startswith('# '):
                    return line[2:].strip()
    except OSError:
        pass
    return fallback


def list_manual_pages(src: str):
    """Sorted markdown pages under ``src``.

    Returns ``[{'rel': <path rel to src, e.g. 'guide/setup.md'>,
    'title': str, 'dir': <subfolder, '' = root>}, ...]``, sorted by ``rel``.
    Non-markdown files are ignored here (they are still copied as assets)."""
    pages = []
    for root, dirs, files in os.walk(src):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, src)
            if not is_markdown(rel):
                continue
            base = os.path.basename(os.path.splitext(name)[0])
            pages.append({
                'rel': rel.replace(os.sep, '/'),
                'title': _title_of(full, base),
                'dir': os.path.dirname(rel).replace(os.sep, '/'),
            })
    pages.sort(key=lambda p: p['rel'])
    return pages


def copy_manual_docs(src, output_dir):
    """Copy ``src`` into ``<output_dir>/manual/`` and return the page list.

    Refuses (warns, returns ``[]``) when the folder is missing or when ``src``
    and ``output_dir`` nest each other (that would recurse forever). The target
    is pruned first, so the copy is always fresh and never stale."""
    if not src or not os.path.isdir(src):
        log(f'manual: folder not found — skipping manual docs: {src!r}')
        return []
    out = _abspath(output_dir)
    if _nested(src, out):
        log(f'manual: refusing — {src} and {out} nest each other; '
            f'skipping manual docs (would copy the output into itself)')
        return []
    os.makedirs(out, exist_ok=True)
    target = os.path.join(out, MANUAL_DIRNAME)
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(src, target)
    pages = list_manual_pages(src)
    log(f'manual: copied {len(pages)} page(s) -> {target}')
    return pages


def manual_payload(pages):
    """JSON-able dict for ``meta/manual.json`` and the web API payload."""
    return {
        'count': len(pages),
        'pages': [{'rel': p['rel'], 'title': p['title'], 'dir': p['dir'],
                   'href': MANUAL_DIRNAME + '/' + p['rel']}
                  for p in pages],
    }


def write_manual_meta(output_dir, pages):
    """Write ``<output_dir>/meta/manual.json`` (the sidebar/API source)."""
    meta_dir = os.path.join(output_dir, 'meta')
    os.makedirs(meta_dir, exist_ok=True)
    path = os.path.join(meta_dir, 'manual.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(manual_payload(pages), fh, ensure_ascii=False, indent=1)
    return path
