"""Guard tests for the manual-docs web routing (web/server.py).

The hard rule: failures must be visible, never silent. These exercise the
server's routing for hand-written docs — markdown pages render, the non-
markdown assets that ship with them are served raw, /api/symbols carries the
manual list, and path traversal stays blocked — so a regression in any of
those surfaces here instead of as a silent 404 / missing sidebar entry.

Run directly (no pytest):  .venv/bin/python tests/test_web_manual.py
"""
import io
import json
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from kodama_docs import manual  # noqa: E402
from web.server import DocsHandler  # noqa: E402


class _FakeReq:
    def makefile(self, mode, *a, **kw):
        return io.BytesIO()


def _handler(docs_root, path):
    """A DocsHandler wired to a docs dir and a single request path, no socket."""
    h = DocsHandler.__new__(DocsHandler)
    h.path = path
    h.requestline = ''
    h.request_version = 'HTTP/1.1'
    h.command = 'GET'
    h.headers = {}
    h.request = _FakeReq()
    h.client_address = ('127.0.0.1', 0)
    h.server = None
    h.wfile = io.BytesIO()
    DocsHandler.docs_root = os.path.realpath(docs_root)
    DocsHandler.web_root = os.path.realpath(os.path.join(REPO, 'web'))
    DocsHandler.default_theme = 'light'
    return h


def _get(docs_root, path):
    h = _handler(docs_root, path)
    h.do_GET()
    raw = h.wfile.getvalue()
    head, _, rest = raw.partition(b'\r\n\r\n')
    status = head.split(b'\r\n')[0].decode('ascii', 'replace')
    ctype = ''
    for line in head.split(b'\r\n'):
        if line.lower().startswith(b'content-type:'):
            ctype = line.split(b':', 1)[1].strip().decode('ascii', 'replace')
    return status, ctype, rest


def _mkdocs():
    d = tempfile.mkdtemp(prefix='webmanual_')
    os.makedirs(os.path.join(d, 'manual', 'img'))
    os.makedirs(os.path.join(d, 'meta'))
    with open(os.path.join(d, 'index.md'), 'w', encoding='utf-8') as fh:
        fh.write('# Index\n\nhello\n')
    with open(os.path.join(d, 'manual', 'intro.md'), 'w', encoding='utf-8') as fh:
        fh.write('# Hello manual\n\nsome **prose**.\n')
    with open(os.path.join(d, 'manual', 'style.css'), 'w', encoding='utf-8') as fh:
        fh.write('body { color: red; }\n')
    with open(os.path.join(d, 'manual', 'img', 'note.txt'), 'w', encoding='utf-8') as fh:
        fh.write('a static asset\n')
    with open(os.path.join(d, 'meta', 'symbols.json'), 'w', encoding='utf-8') as fh:
        json.dump({'name': 't', 'file_count': 0, 'files': []}, fh)
    manual.write_manual_meta(d, manual.list_manual_pages(os.path.join(d, 'manual')))
    return d


def test_manual_md_renders():
    d = _mkdocs()
    status, ctype, body = _get(d, '/manual/intro.md')
    assert '200' in status, status
    assert 'text/html' in ctype, ctype
    assert b'Hello manual' in body, body[:200]
    assert b'<strong>prose</strong>' in body, body[:400]
    print('ok   test_manual_md_renders')


def test_manual_asset_served_raw():
    d = _mkdocs()
    status, ctype, body = _get(d, '/manual/style.css')
    assert '200' in status, status
    assert 'text/css' in ctype, ctype
    assert body == b'body { color: red; }\n', body
    print('ok   test_manual_asset_served_raw')


def test_manual_nested_asset_served_raw():
    d = _mkdocs()
    status, ctype, body = _get(d, '/manual/img/note.txt')
    assert '200' in status, status
    assert body == b'a static asset\n', body
    print('ok   test_manual_nested_asset_served_raw')


def test_symbols_index_includes_manual():
    d = _mkdocs()
    status, ctype, body = _get(d, '/api/symbols')
    assert '200' in status, status
    payload = json.loads(body)
    assert 'manual' in payload, list(payload)
    rels = sorted(p['rel'] for p in payload['manual'])
    # only markdown pages are listed; css/txt assets are not "pages"
    assert rels == ['intro.md'], rels
    assert payload['manual'][0]['href'] == 'manual/intro.md'
    print('ok   test_symbols_index_includes_manual')


def test_manual_traversal_blocked():
    d = _mkdocs()
    status, ctype, body = _get(d, '/manual/../../settings.yaml')
    assert '404' in status or '400' in status, status
    print('ok   test_manual_traversal_blocked')


def test_manual_missing_404():
    d = _mkdocs()
    status, ctype, body = _get(d, '/manual/nope.md')
    assert '404' in status, status
    print('ok   test_manual_missing_404')


def main():
    test_manual_md_renders()
    test_manual_asset_served_raw()
    test_manual_nested_asset_served_raw()
    test_symbols_index_includes_manual()
    test_manual_traversal_blocked()
    test_manual_missing_404()
    print('\n6 web-manual tests passed')


if __name__ == '__main__':
    main()
