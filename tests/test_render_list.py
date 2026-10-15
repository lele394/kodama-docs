"""web/render.py render_list guard tests — bullet lists at any depth.

Run:  .venv/bin/python tests/test_render_list.py

The old implementation only supported two levels (top + one nested) and
emitted unbalanced <li> tags. The index's "Manual documentation" section
now nests as deep as the manual's folders, so render_list must build
properly nested <ul>/<li> for arbitrary depth.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.render import render_list  # noqa: E402


def _balanced(h):
    assert h.count('<ul>') == h.count('</ul>'), h
    assert h.count('<li>') == h.count('</li>'), h
    assert h.startswith('<ul>') and h.endswith('</ul>')


def test_flat_list():
    h = render_list([(0, 'a'), (0, 'b')])
    assert h == ('<ul>\n'
                 '<li>a\n'
                 '</li>\n'
                 '<li>b\n'
                 '</li>\n'
                 '</ul>'), h
    _balanced(h)


def test_two_level_nesting():
    h = render_list([(0, 'a'), (2, 'b'), (2, 'c'), (0, 'd')])
    assert h == ('<ul>\n'
                 '<li>a\n'
                 '<ul>\n'
                 '<li>b\n'
                 '</li>\n'
                 '<li>c\n'
                 '</li>\n'
                 '</ul>\n'
                 '</li>\n'
                 '<li>d\n'
                 '</li>\n'
                 '</ul>'), h
    _balanced(h)


def test_three_level_nesting():
    h = render_list([(0, 'a'), (2, 'b'), (4, 'c'), (2, 'd'), (0, 'e')])
    assert h == ('<ul>\n'
                 '<li>a\n'
                 '<ul>\n'
                 '<li>b\n'
                 '<ul>\n'
                 '<li>c\n'
                 '</li>\n'
                 '</ul>\n'
                 '</li>\n'
                 '<li>d\n'
                 '</li>\n'
                 '</ul>\n'
                 '</li>\n'
                 '<li>e\n'
                 '</li>\n'
                 '</ul>'), h
    _balanced(h)


def test_sibling_branches_stay_separate():
    """Each top-level item keeps its own nested list."""
    h = render_list([(0, 'a'), (2, 'x'), (0, 'b'), (2, 'y')])
    assert h.count('<ul>') == 3 and h.count('<li>') == 4, h
    _balanced(h)


def test_inline_markdown_in_items():
    h = render_list([(0, '**Bold** and [link](u)')])
    assert '<strong>Bold</strong> and <a href="u">link</a>' in h, h


def test_first_item_deeper_than_zero_is_top_level():
    """A list whose first item already has an indent still renders as a
    flat top-level list (no phantom parent)."""
    h = render_list([(2, 'a'), (2, 'b')])
    assert h == ('<ul>\n'
                 '<li>a\n'
                 '</li>\n'
                 '<li>b\n'
                 '</li>\n'
                 '</ul>'), h
    _balanced(h)


def main():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith('test_') and callable(v)]
    for fn in fns:
        fn()
        print(f'ok   {fn.__name__}')
    print(f'\n{len(fns)} render_list tests passed')


if __name__ == '__main__':
    main()
