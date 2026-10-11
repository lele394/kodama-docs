"""doc_maker web server: serves the rendered *.md docs as themed HTML.

Stdlib only (http.server.ThreadingHTTPServer). URLs mirror the docs
directory — a request for ``files/game/main.lua.md`` returns that file
rendered as HTML — so every internal markdown link (relative paths,
``#fn-...`` anchors) keeps working unmodified. Static assets (app.js and
themes/<light|dark>/style.css) come from this web/ folder; the page
button switches themes and the choice is persisted by the server
(web/theme_state.json) so it survives reloads and applies to every
browser. Settings: web/web_settings.yaml next to this file.
"""
import json
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

def _load_template(name: str) -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'templates', name)
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


PAGE = _load_template('page.html')

GRAPH_PAGE = _load_template('graph.html')


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
    theme_state = None  # path of web/theme_state.json (set by serve())
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
        if path in ('/app.js', '/graph.js'):
            return self._webfile(path[1:], 'text/javascript; charset=utf-8')
        if path.startswith('/lib/'):
            name = path[len('/lib/'):]
            ext = name.rsplit('.', 1)[-1] if '.' in name else ''
            ctype = {'js': 'text/javascript; charset=utf-8',
                     'css': 'text/css; charset=utf-8',
                     'txt': 'text/plain; charset=utf-8'}.get(
                ext, 'application/octet-stream')
            return self._webfile('lib/' + name, ctype)
        if path == '/graph':
            return self._graph_page()
        if path == '/api/graph':
            return self._docfile('meta/graph.json',
                                 'application/json; charset=utf-8')
        if path.startswith('/page/') and path.endswith('.md'):
            return self._page_body(path[len('/page/'):])
        if path.endswith('.md'):
            return self._page(path.lstrip('/'))
        return self._error(404, 'not found')

    def do_POST(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/api/theme':
            return self._set_theme()
        return self._error(404, 'not found')

    def _set_theme(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(min(length, 16)).decode('utf-8', 'replace')
        body = body.strip()
        if body not in ('light', 'dark'):
            return self._error(400, 'theme must be light or dark')
        try:
            with open(self.theme_state, 'w', encoding='utf-8') as fh:
                json.dump({'theme': body}, fh)
        except OSError as e:
            return self._error(500, str(e))
        DocsHandler.default_theme = body
        self._send(200, b'ok', 'text/plain; charset=utf-8')

    # ------------------------------------------------------------ handlers
    def _page(self, relpath: str):
        full, md, st = self._load_doc(relpath)
        if full is None:
            return
        body = self._rendered(full, md, st)
        dark = self.default_theme == 'dark'
        page = PAGE.format(title=html_escape(_title(md, relpath)),
                           theme=self.default_theme,
                           hljs_light=' disabled' if dark else '',
                           hljs_dark='' if dark else ' disabled',
                           body=body)
        self._send(200, page.encode('utf-8'), 'text/html; charset=utf-8')

    def _page_body(self, relpath: str):
        """Rendered doc body without the page shell — for the /graph
        left panel."""
        full, md, st = self._load_doc(relpath)
        if full is None:
            return
        body = self._rendered(full, md, st)
        self._send(200, body.encode('utf-8'), 'text/html; charset=utf-8')

    def _load_doc(self, relpath: str):
        """(full_path, md_text, stat) or (None, None, None) — errors sent."""
        full = self._safe(self.docs_root, relpath)
        if full is None or not os.path.isfile(full):
            self._error(404, f'no such doc: {relpath}')
            return None, None, None
        try:
            st = os.stat(full)
            with open(full, 'r', encoding='utf-8') as fh:
                md = fh.read()
        except OSError as e:
            self._error(500, str(e))
            return None, None, None
        return full, md, st

    def _rendered(self, full: str, md: str, st) -> str:
        with self._cache_lock:
            hit = self._cache.get(full)
            if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
                return hit[2]
            body = render_md(md)
            self._cache[full] = (st.st_mtime, st.st_size, body)
            return body

    def _docfile(self, rel: str, ctype: str):
        """Serve a raw file from the docs root (meta/graph.json)."""
        full = self._safe(self.docs_root, rel)
        if full is None or not os.path.isfile(full):
            return self._error(404, f'no such file: {rel}')
        with open(full, 'rb') as fh:
            data = fh.read()
        self._send(200, data, ctype)

    def _graph_page(self):
        dark = self.default_theme == 'dark'
        page = GRAPH_PAGE.format(
            theme=self.default_theme,
            hljs_light=' disabled' if dark else '',
            hljs_dark='' if dark else ' disabled')
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

    def _send(self, code, data, ctype, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
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
    DocsHandler.theme_state = os.path.join(
        DocsHandler.web_root, 'theme_state.json')
    # A theme picked earlier (POST /api/theme) wins over the settings
    # default, so the choice survives server restarts and applies to
    # every browser.
    try:
        with open(DocsHandler.theme_state, 'r', encoding='utf-8') as fh:
            saved = json.load(fh).get('theme')
        if saved in ('light', 'dark'):
            settings['theme'] = saved
    except (OSError, ValueError):
        pass
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
