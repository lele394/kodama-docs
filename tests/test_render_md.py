"""web/render.py markdown subset + safety tests.

Run:  .venv/bin/python tests/test_render_md.py

Manual documentation is arbitrary hand-written Markdown, and generated prose
is model-authored, so the renderer must handle images / ordered lists /
blockquotes and must never pass arbitrary HTML or script URLs through.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kodama_docs.markdown import md_escape  # noqa: E402
from web.render import render_inline, render_md  # noqa: E402


def test_markdown_image():
    out = render_md('![alt text](img/pic.png)\n')
    assert out == '<p><img src="img/pic.png" alt="alt text"></p>', out


def test_image_alt_is_escaped():
    out = render_inline('![<script>](x.png)')
    assert '<script>' not in out, out
    assert '&lt;script&gt;' in out, out


def test_ordered_list():
    out = render_md('1. one\n2. two\n')
    assert '<ol>' in out and '</ol>' in out, out
    assert '<li>one' in out and '<li>two' in out, out


def test_blockquote():
    out = render_md('> developer note\n')
    assert out.startswith('<blockquote>'), out
    assert 'developer note' in out, out


def test_raw_html_is_escaped():
    out = render_inline('<script>alert(1)</script>')
    assert '<script>' not in out, out
    assert '&lt;script&gt;' in out, out


def test_generated_anchor_and_span_pass():
    anchor = '<a id="fn-go-4"></a>'
    span = '<span style="color:#e67e22">unresolved</span>'
    assert render_inline(anchor) == anchor
    assert render_inline(span) == span


def test_script_url_is_rejected():
    out = render_inline('[click](javascript:alert(1))')
    assert 'javascript:' not in out, out
    assert 'href="#"' in out, out


def test_link_label_is_escaped():
    out = render_inline('[<script>](x.md)')
    assert '<script>' not in out, out
    assert '&lt;script&gt;' in out, out


def test_table_escape_flattens_newlines():
    out = md_escape('line one\nline two | piped')
    assert '\n' not in out, out
    assert out == 'line one line two \\| piped', out


def main():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith('test_') and callable(v)]
    for fn in fns:
        fn()
        print(f'ok   {fn.__name__}')
    print(f'\n{len(fns)} render_md tests passed')


if __name__ == '__main__':
    main()
