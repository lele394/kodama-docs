"""Manual-documentation unit tests (no LLM, temp folders).

Run:  .venv/bin/python tests/test_manual.py

Covers the ``project.manual_doc`` feature (kodama_docs/manual.py):
  * only markdown files become pages; non-md files are assets;
  * pages are sorted and carry a title + subfolder;
  * copy creates ``output/manual/`` with all contents (md + assets);
  * missing folder -> no pages, no crash;
  * nested src/output guard -> refused;
  * the meta payload shape is stable.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kodama_docs import manual  # noqa: E402


def _tree(base, files):
    for rel, content in files.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p) or base, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write(content)


def test_list_marks_only_md_sorted():
    with tempfile.TemporaryDirectory() as d:
        _tree(d, {
            'zz.md': '# Zeta\n',
            'alpha.md': 'no heading here\n',
            'guide/setup.md': '# Setup\n',
            'code.lua': 'print(1)',
            'assets/style.css': 'body {}',
        })
        pages = manual.list_manual_pages(d)
        assert [p['rel'] for p in pages] == ['alpha.md', 'guide/setup.md',
                                             'zz.md'], [p['rel'] for p in pages]
        titles = {p['rel']: p['title'] for p in pages}
        assert titles['zz.md'] == 'Zeta'
        assert titles['alpha.md'] == 'alpha'      # falls back to the basename
        assert titles['guide/setup.md'] == 'Setup'
        dirs = {p['rel']: p['dir'] for p in pages}
        assert dirs['alpha.md'] == ''
        assert dirs['guide/setup.md'] == 'guide'


def test_copy_creates_manual_dir_with_assets():
    with tempfile.TemporaryDirectory() as src, \
            tempfile.TemporaryDirectory() as out:
        _tree(src, {'a.md': '# A\n', 'img.bin': 'x', 'guide/b.md': '# B\n'})
        pages = manual.copy_manual_docs(src, out)
        target = os.path.join(out, manual.MANUAL_DIRNAME)
        assert os.path.isfile(os.path.join(target, 'a.md'))
        assert os.path.isfile(os.path.join(target, 'img.bin'))
        assert os.path.isfile(os.path.join(target, 'guide', 'b.md'))
        assert [p['rel'] for p in pages] == ['a.md', 'guide/b.md']


def test_copy_is_fresh_each_run():
    """A file removed from the source folder must not survive a re-copy."""
    with tempfile.TemporaryDirectory() as src, \
            tempfile.TemporaryDirectory() as out:
        _tree(src, {'keep.md': '# K\n', 'gone.md': '# G\n'})
        manual.copy_manual_docs(src, out)
        os.remove(os.path.join(src, 'gone.md'))
        pages = manual.copy_manual_docs(src, out)
        assert [p['rel'] for p in pages] == ['keep.md']
        assert not os.path.exists(
            os.path.join(out, manual.MANUAL_DIRNAME, 'gone.md'))


def test_copy_missing_folder_skips():
    with tempfile.TemporaryDirectory() as out:
        pages = manual.copy_manual_docs('/no/such/folder', out)
        assert pages == []
        assert not os.path.exists(os.path.join(out, manual.MANUAL_DIRNAME))


def test_copy_nested_guard():
    # source inside output_dir -> refuse (would copy the output into itself)
    with tempfile.TemporaryDirectory() as out:
        src = os.path.join(out, 'manual_src')
        os.makedirs(src)
        assert manual.copy_manual_docs(src, out) == []
    # output_dir inside source -> refuse for the same reason
    with tempfile.TemporaryDirectory() as src:
        out = os.path.join(src, 'out')
        os.makedirs(out)
        assert manual.copy_manual_docs(src, out) == []


def test_payload_shape():
    pages = [{'rel': 'a.md', 'title': 'A', 'dir': ''}]
    pl = manual.manual_payload(pages)
    assert pl['count'] == 1
    assert pl['pages'][0] == {'rel': 'a.md', 'title': 'A', 'dir': '',
                              'href': 'manual/a.md'}


def test_write_manual_meta_roundtrip():
    import json
    with tempfile.TemporaryDirectory() as out:
        pages = [{'rel': 'a.md', 'title': 'A', 'dir': ''},
                 {'rel': 'guide/b.md', 'title': 'B', 'dir': 'guide'}]
        path = manual.write_manual_meta(out, pages)
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        assert data['count'] == 2
        assert data['pages'][1]['href'] == 'manual/guide/b.md'


def main():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith('test_') and callable(v)]
    for fn in fns:
        fn()
        print(f'ok   {fn.__name__}')
    print(f'\n{len(fns)} manual tests passed')


if __name__ == '__main__':
    main()
