"""Static-site builder tests (kodama_docs/static_site.py).

Run:  .venv/bin/python tests/test_static_site.py

Guards the no-server output: the layout, the depth-aware base prefix,
the JS switch (window.__KODAMA_BASE__), the baked-in theme, the internal
.md -> .html link rewrite, the slim symbols payload, and verbatim manual
assets. The fake webdir reuses the REAL templates, so template regressions
(missing placeholder, wrong asset prefix) surface here too.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from kodama_docs import static_site  # noqa: E402

FAILS = []


def check(cond, msg):
    if cond:
        print(f'ok   {msg}')
    else:
        print(f'FAIL {msg}')
        FAILS.append(msg)


def _tree(base, files):
    for rel, content in files.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p) or base, exist_ok=True)
        with open(p, 'wb' if isinstance(content, bytes) else 'w',
                  encoding=None if isinstance(content, bytes) else 'utf-8') as fh:
            fh.write(content)


def _read(p):
    with open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


# ------------------------------------------------------------- pure bits
def test_base_for():
    check(static_site.base_for('index.html') == '', 'base_for(index) is empty')
    check(static_site.base_for('files/a.html') == '../', 'base_for(files) is ../')
    check(static_site.base_for('files/a/b.html') == '../../',
          'base_for(deep file) is ../../')
    check(static_site.base_for('manual/x/y.html') == '../../',
          'base_for(manual page) is ../../')


def test_rewrite_md_links():
    rw = static_site.rewrite_md_links
    check(rw('<a href="x.md">') == '<a href="x.html">', 'plain .md -> .html')
    check(rw('<a href="x.md#a">') == '<a href="x.html#a">', 'fragment kept')
    check(rw('<a href="../y.md#b">') == '<a href="../y.html#b">',
          'relative link + fragment')
    ext = '<a href="https://e.com/x.md">'
    check(rw(ext) == ext, 'https link untouched')
    rel = '<a href="//cdn/x.md">'
    check(rw(rel) == rel, 'protocol-relative link untouched')
    check(rw('<a href="#a">') == '<a href="#a">', 'anchor untouched')
    check(rw('<a href="g/01%20-%20P.md#c">')
          == '<a href="g/01%20-%20P.html#c">', '%20-encoded link rewritten')


# ---------------------------------------------------------------- fixture
def build_fixture(root):
    docs = os.path.join(root, 'docs')
    _tree(docs, {
        'index.md': ('# Home\n\nSee [the file](files/src/a.md), the '
                     '[sibling](files/src/a.md#fn-go-4), the '
                     '[manual](manual/g/01%20-%20Page.md#anchor), and an '
                     '[external](https://example.com/x.md) link.\n'),
        'files/src/a.md': ('# A\n\nBack [home](../../index.md), '
                           '[sibling](../b.md#fn-go-4).\n'),
        'files/b.md': '# B\n\n[home](../index.md)\n',
        'manual/g/01 - Page.md': '# Page\n',
        'manual/img/pic.png': b'PNGDATA',
        'meta/symbols.json': json.dumps({
            'schema': 'kodama_docs/symbols@1',
            'file_count': 2,
            'files': [
                {'relpath': 'src/a.md', 'lines': 10,
                 'functions': [{'name': 'go', 'qualified': 'go', 'line': 4},
                               {'name': 'other', 'qualified': 'other',
                                'line': 9, 'body': 'SECRET-BODY-TEXT'}],
                 'file_vars': [{'name': 'X', 'line': 1}],
                 'calls': ['MUST-NOT-LEAK'], 'imports': ['MUST-NOT-LEAK2'],
                 'classes': ['MUST-NOT-LEAK3']},
                {'relpath': 'b.md', 'lines': 2, 'functions': [],
                 'file_vars': []},
            ]}, indent=1),
        'meta/graph.json': json.dumps({'directed': True, 'nodes': [],
                                       'edges': []}),
        'meta/manual.json': json.dumps({
            'count': 1,
            'pages': [{'rel': 'g/01 - Page.md', 'title': 'Page', 'dir': 'g',
                       'href': 'manual/g/01 - Page.md'}]}),
    })

    webdir = os.path.join(root, 'web')
    os.makedirs(os.path.join(webdir, 'templates'), exist_ok=True)
    for name in ('page.html', 'graph.html'):
        shutil.copy2(os.path.join(REPO, 'web', 'templates', name),
                     os.path.join(webdir, 'templates', name))
    _tree(webdir, {
        'web_settings.yaml': 'host: 127.0.0.1\ndefault_theme: dark\n',
        'app.js': '// stub app\n',
        'sidebar.js': '// stub sidebar\n',
        'fuzzy.js': '// stub fuzzy\n',
        'graph.js': '// stub graph\n',
        'graph/state.js': '// stub state\n',
        'lib/hi.css': '/* stub lib */\n',
        'themes/light/style.css': '/* light */\n',
        'themes/dark/style.css': '/* dark */\n',
    })
    return docs, webdir


def main():
    test_base_for()
    test_rewrite_md_links()

    with tempfile.TemporaryDirectory() as tmp:
        docs, webdir = build_fixture(tmp)
        cfg = {'output_dir': docs, 'data_dir': os.path.join(docs, 'data')}

        site = static_site.build(cfg, webdir=webdir)
        check(site == os.path.join(docs, 'site'), 'site lives in <out>/site')

        # ---- layout ------------------------------------------------------
        for rel in (
                'index.html', 'graph.html', '404.html',
                'files/src/a.html', 'files/b.html',
                'manual/g/01 - Page.html', 'manual/img/pic.png',
                'app.js', 'sidebar.js', 'fuzzy.js', 'graph.js',
                'graph/state.js', 'lib/hi.css',
                'theme/dark/style.css', 'theme/light/style.css',
                'symbols.json', 'graph.json',
        ):
            check(os.path.isfile(os.path.join(site, rel)), f'present: {rel}')

        # ---- theme (dark, from the fixture web_settings.yaml) -----------
        idx = _read(os.path.join(site, 'index.html'))
        check('theme/dark/style.css' in idx, 'index: dark theme baked in')
        check('theme/light/style.css' not in idx,
              'index: no light theme reference')
        check('href="lib/github.min.css" disabled>' in idx,
              'index: light hljs css disabled')
        check('href="lib/github-dark.min.css">' in idx
              and 'lib/github-dark.min.css" disabled>' not in idx,
              'index: dark hljs css enabled')

        # ---- JS switch + base prefix -------------------------------------
        check('window.__KODAMA_BASE__ = \'\'' in idx,
              'index: __KODAMA_BASE__ is empty string (site root)')
        a = _read(os.path.join(site, 'files/src/a.html'))
        check('window.__KODAMA_BASE__ = \'../../\'' in a,
              'file page: __KODAMA_BASE__ = ../../ (depth 2)')
        check('href="../../index.html"' in a,
              'file page: brand -> ../../index.html')
        check('src="../../sidebar.js"' in a, 'file page: sidebar.js prefixed')
        check('href="../../theme/dark/style.css?v=2"' in a,
              'file page: theme css prefixed')
        check('href="../../lib/github-dark.min.css">' in a,
              'file page: hljs css prefixed')
        m = _read(os.path.join(site, 'manual/g/01 - Page.html'))
        check('window.__KODAMA_BASE__ = \'../../\'' in m,
              'manual page: __KODAMA_BASE__ = ../../')
        check('href="../../index.html"' in m,
              'manual page: brand -> ../../index.html')
        check('href="../../graph.html"' in m,
              'manual page: nav -> ../../graph.html')

        # ---- nav / brand / graph page ------------------------------------
        check('<a class="brand" href="index.html">' in idx,
              'index: brand -> index.html')
        check('<a class="nav" href="graph.html">graph</a>' in idx,
              'index: nav -> graph.html')
        g = _read(os.path.join(site, 'graph.html'))
        check('window.__KODAMA_BASE__ = \'\'' in g, 'graph: base empty')
        check('<a class="brand" href="index.html">' in g,
              'graph: brand -> index.html')
        check('src="graph.js"' in g, 'graph: module script relative')

        # ---- title --------------------------------------------------------
        check('<title>Home</title>' in idx, 'index: title from first h1')
        check('<title>A</title>' in a, 'file page: title from first h1')
        check('<title>Page</title>' in m, 'manual page: title from first h1')
        b = _read(os.path.join(site, 'files/b.html'))
        check('<title>B</title>' in b, 'second file page: title from h1')

        # ---- link rewrite --------------------------------------------------
        check('href="files/src/a.html"' in idx, 'index: .md link -> .html')
        check('href="files/src/a.html#fn-go-4"' in idx,
              'index: fragment link rewritten')
        check('href="manual/g/01%20-%20Page.html#anchor"' in idx,
              'index: manual link rewritten')
        check('href="https://example.com/x.md"' in idx,
              'index: external link untouched')
        check('href="../b.html#fn-go-4"' in a,
              'file page: sibling .md link rewritten')
        check('href="../index.html"' in b,
              'file page: parent .md link rewritten')

        # ---- symbols payload (slim: no bodies, no extra fields) ----------
        sl = json.loads(_read(os.path.join(site, 'symbols.json')))
        check(sl['file_count'] == 2, 'symbols: file_count')
        f0 = sl['files'][0]
        check(f0['functions'] == [
            {'name': 'go', 'qualified': 'go', 'line': 4},
            {'name': 'other', 'qualified': 'other', 'line': 9}],
            'symbols: functions slim to name/qualified/line')
        check(f0['vars'] == [{'name': 'X', 'line': 1}],
              'symbols: vars slim to name/line')
        blob = _read(os.path.join(site, 'symbols.json'))
        check('SECRET-BODY-TEXT' not in blob and 'MUST-NOT-LEAK' not in blob,
              'symbols: no bodies or graph edges shipped')
        check(sl['manual'] == [
            {'rel': 'g/01 - Page.md', 'title': 'Page', 'dir': 'g',
             'href': 'manual/g/01 - Page.md'}],
            'symbols: manual list merged in')
        check(json.loads(_read(os.path.join(site, 'graph.json')))
              == {'directed': True, 'nodes': [], 'edges': []},
              'graph.json copied')

        # ---- verbatim manual asset -----------------------------------------
        with open(os.path.join(site, 'manual/img/pic.png'), 'rb') as fh:
            check(fh.read() == b'PNGDATA', 'manual asset copied verbatim')

        # ---- 404 ------------------------------------------------------------
        nf = _read(os.path.join(site, '404.html'))
        check('<a href="index.html">Back to the docs home</a>' in nf,
              '404: links back to the index')
        check('theme/dark/style.css' in nf, '404: same baked-in theme')
        check('lib/github.min.css" disabled>' in nf,
              '404: light hljs css disabled')

    # ---- theme fallbacks ---------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        docs, webdir = build_fixture(tmp)
        # no web_settings.yaml, no theme_state.json -> light
        os.remove(os.path.join(webdir, 'web_settings.yaml'))
        static_site.build({'output_dir': docs}, webdir=webdir)
        idx = _read(os.path.join(docs, 'site', 'index.html'))
        check('theme/light/style.css' in idx, 'fallback: light without config')
        # theme_state.json (server's {"theme": ...} format) is the fallback
        with open(os.path.join(webdir, 'theme_state.json'), 'w') as fh:
            fh.write('{"theme": "dark"}')
        static_site.build({'output_dir': docs}, webdir=webdir)
        idx = _read(os.path.join(docs, 'site', 'index.html'))
        check('theme/dark/style.css' in idx, 'fallback: theme_state.json')

    # ---- CLI -----------------------------------------------------------------
    help_txt = subprocess.run(
        [sys.executable, os.path.join(REPO, 'main.py'), '--help'],
        capture_output=True, text=True, cwd=REPO).stdout
    check('--static' in help_txt, 'main.py --help lists --static')

    print()
    if FAILS:
        print(f'{len(FAILS)} assertion(s) FAILED')
        sys.exit(1)
    print('all static-site tests passed')


if __name__ == '__main__':
    main()
