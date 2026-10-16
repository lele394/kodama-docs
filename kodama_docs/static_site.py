"""Static site builder: a self-contained ``site/`` folder, no server needed.

See STATIC_SITE.md for the full design. The output mirrors the output dir:
``index.md -> index.html``, ``files/<rel>.md -> files/<rel>.html``,
``manual/<rel>.md -> manual/<rel>.html``, plus ``graph.html``, ``404.html``
and everything the web UI needs at the site root (the root mirrors the
server's URL space: app.js, sidebar.js, graph.js, graph/, lib/, theme/,
icon/, and the ``symbols.json`` / ``graph.json`` data the server would
otherwise serve via ``/api/*``). All paths are relative and depth-aware, so
the folder works at any host subpath (GitHub Pages) and over ``file://``
(content pages).
"""
import json
import os
import re
import shutil
import sys

from kodama_docs.util import log

try:  # repo layout: web/ is a top-level package next to kodama_docs/
    from web.render import render_md
except ImportError:  # pragma: no cover - layout fallback
    _webdir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'web')
    if _webdir not in sys.path:
        sys.path.append(_webdir)
    from render import render_md  # type: ignore

# internal hrefs look like href="x.md" / href="../x.md" / href="x.md#anchor";
# absolute http(s)://, mailto:, #anchors and data: stay untouched.
_HREF_MD_RE = re.compile(r'href="([^"<>?]+?\.md)(#[^"]*)?"')

_JS_FILES = ('app.js', 'sidebar.js', 'fuzzy.js', 'graph.js')


def _read(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def base_for(rel_html: str) -> str:
    """Relative prefix from a site-relative page path to the site root:
    index.html -> '', files/a.html -> '../', manual/x/y.html -> '../../'."""
    return '../' * rel_html.count('/')


def rewrite_md_links(body: str) -> str:
    """Internal ``href="….md"`` -> ``….html`` (fragments preserved); external
    and anchor-only links untouched."""
    def fix(m):
        target, frag = m.group(1), m.group(2) or ''
        low = target.lower()
        if (low.startswith(('http://', 'https://', 'mailto:', 'javascript:',
                            'data:', '//')) or target.startswith('#')):
            return m.group(0)
        return f'href="{target[:-3]}.html{frag}"'

    return _HREF_MD_RE.sub(fix, body)


def _theme_default(webdir: str) -> str:
    """Baked-in theme: web/web_settings.yaml default_theme, else the last
    --serve choice (web/theme_state.json), else 'light'."""
    def from_text(text: str):
        m = re.search(r'^\s*default_theme:\s*(\S+)', text, re.M)
        if m and m.group(1).lower() in ('light', 'dark'):
            return m.group(1).lower()
        return None

    settings = os.path.join(webdir, 'web_settings.yaml')
    if os.path.isfile(settings):
        theme = from_text(_read(settings))
        if theme:
            return theme
    state = os.path.join(webdir, 'theme_state.json')
    if os.path.isfile(state):
        # the server writes {"theme": "light"|"dark"} (see web/server.py)
        try:
            t = json.loads(_read(state)).get('theme')
            if t in ('light', 'dark'):
                return t
        except (ValueError, AttributeError):
            pass
    return 'light'


def _load_template(webdir: str, name: str) -> str:
    return _read(os.path.join(webdir, 'templates', name))


def _render_page(md: str, title: str, theme: str, base: str,
                 index_href: str, graph_href: str, page_tpl: str) -> str:
    dark = theme == 'dark'
    return page_tpl.format(
        title=title,
        theme=theme,
        hljs_light=' disabled' if dark else '',
        hljs_dark='' if dark else ' disabled',
        base=base, index_href=index_href, graph_href=graph_href,
        # JS static-mode switch (see web/sidebar.js); under --serve the
        # server renders the same slot as `undefined`
        base_json=f"'{base}'",
        body=rewrite_md_links(md))


def slim_symbols(meta_symbols: dict, manual_pages: list) -> dict:
    """The sidebar index: same slim shape the server's /api/symbols builds
    (names + lines only — function bodies never ship to the browser)."""
    return {
        'file_count': meta_symbols.get('file_count') or 0,
        'files': [
            {'relpath': f.get('relpath'),
             'lines': f.get('lines'),
             'functions': [{'name': s.get('name'),
                            'qualified': s.get('qualified'),
                            'line': s.get('line')}
                           for s in (f.get('functions') or [])],
             'vars': [{'name': v.get('name'),
                       'line': v.get('line')}
                      for v in (f.get('file_vars') or [])]}
            for f in (meta_symbols.get('files') or [])],
        'manual': manual_pages,
    }


def _copy_assets(webdir: str, root: str) -> None:
    """Copy the UI so the site root mirrors the server's URL space:
    /app.js /sidebar.js /fuzzy.js /graph.js /graph/* /lib/* and /icon/...
    map to the same relative paths; /theme/<t>/... (which the server
    resolves from web/themes/) becomes theme/<t>/... here."""
    for name in _JS_FILES:
        shutil.copy2(os.path.join(webdir, name), os.path.join(root, name))
    gjs = os.path.join(webdir, 'graph')
    if os.path.isdir(gjs):
        shutil.copytree(gjs, os.path.join(root, 'graph'))
    lib = os.path.join(webdir, 'lib')
    if os.path.isdir(lib):
        shutil.copytree(lib, os.path.join(root, 'lib'))
    themes = os.path.join(webdir, 'themes')
    if os.path.isdir(themes):
        shutil.copytree(themes, os.path.join(root, 'theme'))
    # the icon lives at the repo root (next to kodama_docs/ and web/)
    icondir = os.path.join(os.path.dirname(webdir), 'icon')
    if os.path.isdir(icondir):
        icon_dst = os.path.join(root, 'icon')
        os.makedirs(icon_dst, exist_ok=True)
        for name in ('icon.ico', 'icon.png'):
            src = os.path.join(icondir, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(icon_dst, name))


def _write_json(path: str, obj) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write('\n')


def _iter_doc_pages(out: str):
    """Yields (src, site_rel, is_page) for everything that becomes part of
    the site: index.md, files/*.md, manual/*.md (pages), and non-markdown
    files under manual/ (assets, copied verbatim). site_rel is
    site-relative with forward slashes."""
    def rel(p: str) -> str:
        return os.path.relpath(p, out).replace(os.sep, '/')

    index_md = os.path.join(out, 'index.md')
    if os.path.isfile(index_md):
        yield index_md, 'index.md', True
    for sub in ('files', 'manual'):
        root = os.path.join(out, sub)
        if not os.path.isdir(root):
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(dirpath, name)
                yield full, rel(full), name.lower().endswith('.md')


def default_webdir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'web')


def build(cfg: dict, webdir: str = None) -> str:
    """Build ``<output_dir>/site/`` and return its path. ``webdir``
    defaults to the repo's ``web/`` (templates + UI assets); it is a
    parameter so tests can point at a fixture."""
    out = os.path.abspath(cfg['output_dir'])
    if not os.path.isfile(os.path.join(out, 'index.md')):
        raise SystemExit('static: no index.md in '
                         f'{out} — run the pipeline first (without --serve)')
    webdir = webdir or default_webdir()
    if not os.path.isdir(os.path.join(webdir, 'templates')):
        raise SystemExit(f'static: web/ template dir not found under {webdir}')

    site = os.path.join(out, 'site')
    if os.path.isdir(site):
        shutil.rmtree(site)  # fresh every time (same policy as the manual copy)
    os.makedirs(site)

    theme = _theme_default(webdir)
    page_tpl = _load_template(webdir, 'page.html')
    graph_tpl = _load_template(webdir, 'graph.html')

    # 1. UI assets (mirroring the server's URL space, see _copy_assets) ---
    _copy_assets(webdir, site)

    # 2. data (what /api/symbols and /api/graph would serve) --------------
    meta = os.path.join(out, 'meta')
    manual_pages = []
    manual_json = os.path.join(meta, 'manual.json')
    if os.path.isfile(manual_json):
        try:
            with open(manual_json, 'r', encoding='utf-8') as fh:
                manual_pages = json.load(fh).get('pages', [])
        except (OSError, ValueError):
            manual_pages = []
    symbols_src = os.path.join(meta, 'symbols.json')
    if os.path.isfile(symbols_src):
        with open(symbols_src, 'r', encoding='utf-8') as fh:
            _write_json(os.path.join(site, 'symbols.json'),
                        slim_symbols(json.load(fh), manual_pages))
    else:
        log('static: warning — no meta/symbols.json; sidebar search will '
            'find nothing (run the pipeline first)')
    graph_src = os.path.join(meta, 'graph.json')
    if os.path.isfile(graph_src):
        shutil.copy2(graph_src, os.path.join(site, 'graph.json'))
    else:
        log('static: warning — no meta/graph.json; the graph view will '
            'show an empty-state hint')

    # 3. pages (+ verbatim manual assets) ---------------------------------
    pages = 0
    for src, site_rel, is_page in _iter_doc_pages(out):
        if not is_page:
            # non-markdown manual asset: verbatim copy, same relative place,
            # so its links (../page.html, img.png) keep working
            dst = os.path.join(site, *site_rel.split('/'))
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            shutil.copy2(src, dst)
            continue
        dst_rel = site_rel[:-3] + '.html'
        dst = os.path.join(site, *dst_rel.split('/'))
        os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
        md = _read(src)
        m = re.search(r'^#\s+(.*)$', md, re.M)
        title = (m.group(1).strip() if m
                 else os.path.splitext(os.path.basename(src))[0])
        base = base_for(dst_rel)
        with open(dst, 'w', encoding='utf-8') as fh:
            fh.write(_render_page(
                render_md(md), title, theme, base,
                base + 'index.html', base + 'graph.html', page_tpl))
        pages += 1

    # 4. graph.html + 404.html --------------------------------------------
    with open(os.path.join(site, 'graph.html'), 'w', encoding='utf-8') as fh:
        fh.write(graph_tpl.format(
            theme=theme,
            hljs_light=' disabled' if theme == 'dark' else '',
            hljs_dark='' if theme == 'dark' else ' disabled',
            base='', index_href='index.html', base_json="''"))
    dark = theme == 'dark'
    with open(os.path.join(site, '404.html'), 'w', encoding='utf-8') as fh:
        fh.write(f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found — kodama-docs</title>
<link rel="icon" type="image/x-icon" href="icon/icon.ico">
<link rel="icon" type="image/png" href="icon/icon.png">
<link rel="stylesheet" href="theme/{theme}/style.css?v=2">
<link rel="stylesheet"
      href="lib/github.min.css"{' disabled' if dark else ''}>
<link rel="stylesheet"
      href="lib/github-dark.min.css"{' disabled' if dark else ''}>
</head>
<body>
<div style="max-width:520px;margin:15vh auto;padding:0 1rem;text-align:center">
<h1 style="margin-bottom:.2em">404</h1>
<p>That page does not exist in this documentation site.</p>
<p><a href="index.html">Back to the docs home</a></p>
</div>
</body>
</html>
''')

    # 5. report ------------------------------------------------------------
    log(f'static: {pages} page(s) + graph.html -> {site}')
    log('static: fully self-contained — open site/index.html directly, or '
        'host the folder (GitHub Pages: point Pages at site/)')
    return site


if __name__ == '__main__':  # manual invocation with an explicit config
    from kodama_docs.config import load_config
    build(load_config(sys.argv[1] if len(sys.argv) > 1 else 'settings.yaml'))
