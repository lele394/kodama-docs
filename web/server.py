"""doc_maker web server: serves the rendered *.md docs as themed HTML.

Stdlib only (http.server.ThreadingHTTPServer). URLs mirror the docs
directory — a request for ``files/game/main.lua.md`` returns that file
rendered as HTML — so every internal markdown link (relative paths,
``#fn-...`` anchors) keeps working unmodified. Static assets (app.js and
themes/<light|dark>/style.css) come from this web/ folder; the page
button switches themes and remembers the choice per browser
(localStorage). Settings: web/web_settings.yaml next to this file.
"""
import os
import threading

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import ruamel.yaml

try:
    from .render import render_md
    from util import log
except ImportError:  # run as a plain script from inside web/
    from render import render_md

    def log(msg):
        print(msg, flush=True)

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link id="doc-theme" rel="stylesheet" href="/theme/{theme}/style.css">
<script src="/app.js" defer></script>
</head>
<body>
<header class="topbar">
  <span class="brand">doc_maker</span>
  <button id="theme-toggle" type="button"></button>
</header>
<main class="page">
{body}
</main>
</body>
</html>
"""


def load_settings(path: str) -> dict:
    yaml = ruamel.yaml.YAML()
    with open(path, 'r', encoding='utf-8') as fh:
        raw = yaml.load(fh)
    base = os.path.dirname(os.path.abspath(path))
    theme = str(raw.get('default_theme') or 'light').strip().lower()
    if theme not in ('light', 'dark'):
        raise SystemExit(f'web_settings: default_theme must be light or '
                         f'dark (got {theme!r})')
    docs_dir = raw.get('docs_dir')
    if docs_dir:
        docs_dir = str(docs_dir)
        if not os.path.isabs(docs_dir):
            docs_dir = os.path.normpath(os.path.join(base, docs_dir))
    return {
        'host': str(raw.get('host') or '127.0.0.1'),
        'port': int(raw.get('port') or 8123),
        'theme': theme,
        'docs_dir': docs_dir,
    }


def _title(md: str, relpath: str) -> str:
    for line in md.split('\n'):
        if line.startswith('# '):
            return line[2:].strip()
    return relpath


class DocsHandler(BaseHTTPRequestHandler):
    server_version = 'docmaker'
    timeout = 30
    # bound by serve():
    docs_root = None
    web_root = None
    default_theme = 'light'
    _cache = {}
    _cache_lock = threading.Lock()

    def log_message(self, fmt, *args):
        log(f'web: {self.address_string()} {fmt % args}')

    # ------------------------------------------------------------ dispatch
    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/':
            return self._redirect('/index.md')
        if path.startswith('/theme/') and path.endswith('.css'):
            return self._webfile('themes/' + path[len('/theme/'):],
                                 'text/css; charset=utf-8')
        if path == '/app.js':
            return self._webfile('app.js', 'text/javascript; charset=utf-8')
        if path.endswith('.md'):
            return self._page(path.lstrip('/'))
        return self._error(404, 'not found')

    # ------------------------------------------------------------ handlers
    def _page(self, relpath: str):
        full = self._safe(self.docs_root, relpath)
        if full is None or not os.path.isfile(full):
            return self._error(404, f'no such doc: {relpath}')
        try:
            st = os.stat(full)
            with open(full, 'r', encoding='utf-8') as fh:
                md = fh.read()
        except OSError as e:
            return self._error(500, str(e))
        with self._cache_lock:
            hit = self._cache.get(full)
            if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
                body = hit[2]
            else:
                body = render_md(md)
                self._cache[full] = (st.st_mtime, st.st_size, body)
        page = PAGE.format(title=html_escape(_title(md, relpath)),
                           theme=self.default_theme, body=body)
        self._send(200, page.encode('utf-8'), 'text/html; charset=utf-8')

    def _webfile(self, filename: str, ctype: str):
        full = self._safe(self.web_root, filename)
        if full is None or not os.path.isfile(full):
            return self._error(404, 'not found')
        with open(full, 'rb') as fh:
            data = fh.read()
        self._send(200, data, ctype)

    # ------------------------------------------------------------ plumbing
    @staticmethod
    def _safe(root: str, rel: str):
        """Join + guarantee the result stays under root (no traversal)."""
        full = os.path.realpath(os.path.join(root, rel.lstrip('/')))
        root = os.path.realpath(root)
        if full != root and not full.startswith(root + os.sep):
            return None
        return full

    def _send(self, code, data, ctype):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code, msg):
        body = (f'<!doctype html><meta charset="utf-8">'
                f'<link rel="stylesheet" href="/theme/{self.default_theme}'
                f'/style.css"><body><h1>{code}</h1><p>{msg}</p>'
                f'<p><a href="/index.md">back to index</a></body>').encode()
        self._send(code, body, 'text/html; charset=utf-8')

    def _redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()


def html_escape(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))


def serve(docs_dir: str, settings: dict, web_root: str):
    """Run the docs server until Ctrl-C (blocks)."""
    if not os.path.isfile(os.path.join(docs_dir, 'index.md')):
        raise SystemExit(f'web: no index.md in {docs_dir} — '
                         f'run doc_maker (without --serve) first')
    DocsHandler.docs_root = os.path.realpath(docs_dir)
    DocsHandler.web_root = os.path.realpath(web_root)
    DocsHandler.default_theme = settings['theme']
    host, port = settings['host'], settings['port']
    httpd = ThreadingHTTPServer((host, port), DocsHandler)
    httpd.daemon_threads = True
    shown = host if host not in ('0.0.0.0', '::') else '127.0.0.1'
    log(f'web: serving docs from {docs_dir}')
    log(f'web: http://{shown}:{port}/  (Ctrl-C to stop)')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    log('web: stopped')
