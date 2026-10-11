"""Deterministic Markdown -> HTML for the subset doc_maker generates.

Supports exactly what documentation.py emits: headings (including raw
``<a id="...">`` anchors), paragraphs, **bold**, *italic*, `code`,
[links](url), fenced code blocks (wrapped in closed-by-default
``<details>`` zones, with a following "Call graph" list in its own
zone), two-level bullet lists, tables (with ``\\|`` escaped pipes) and
``---`` rules. Output is a pure function of the input text; no
third-party dependencies (syntax highlighting is client-side
highlight.js, loaded by the page).
"""
import html
import re

_TAG_RE = re.compile(r'<[^<>\n]+>')
_CODE_RE = re.compile(r'`([^`\n]+)`')
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_STAR_RE = re.compile(r'\*([^*\n]+)\*')
_UNDER_RE = re.compile(r'(?<!\w)_([^_\n]+)_(?!\w)')
_INTRA_U_RE = re.compile(r'(?<=\w)_(?=\w)')
_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')
_STASH_RE = re.compile(r'\x00(\d+)\x00')
_HEAD_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_HR_RE = re.compile(r'^-{3,}\s*$')


def render_inline(text: str) -> str:
    """Inline markdown -> HTML (raw tags pass through, code stays literal)."""
    stash = []

    def keep(m):
        stash.append(m.group(0))
        return f'\x00{len(stash) - 1}\x00'

    text = _TAG_RE.sub(keep, text)   # raw anchors like <a id="fn-x-3">
    text = _CODE_RE.sub(keep, text)  # `inline code` content stays literal
    text = html.escape(text)
    text = _BOLD_RE.sub(r'<strong>\1</strong>', text)
    text = _STAR_RE.sub(r'<em>\1</em>', text)
    # protect intraword underscores (e.g. doc_maker) from the italic pass,
    # like GFM's intraword rule
    u_stash = []

    def keep_u(m):
        u_stash.append('_')
        return f'\x01{len(u_stash) - 1}\x01'

    text = _INTRA_U_RE.sub(keep_u, text)
    text = _UNDER_RE.sub(r'<em>\1</em>', text)
    text = re.sub(r'\x01(\d+)\x01', lambda m: '_', text)
    text = _LINK_RE.sub(r'<a href="\2">\1</a>', text)

    def restore(m):
        item = stash[int(m.group(1))]
        if item.startswith('<'):
            return item
        return '<code>' + html.escape(item[1:-1]) + '</code>'

    return _STASH_RE.sub(restore, text)


def _table_cells(row: str) -> list:
    r = row.strip()
    if r.startswith('|'):
        r = r[1:]
    if r.endswith('|'):
        r = r[:-1]
    return [part.replace('\\|', '|').strip()
            for part in re.split(r'(?<!\\)\|', r)]


def render_table(rows) -> str:
    header = _table_cells(rows[0])
    body = [_table_cells(r) for r in rows[2:]] if len(rows) >= 3 else []
    h = ['<table>', '<thead><tr>']
    h += [f'<th>{render_inline(c)}</th>' for c in header]
    h += ['</tr></thead>', '<tbody>']
    for row in body:
        h.append('<tr>' + ''.join(f'<td>{render_inline(c)}</td>' for c in row)
                 + '</tr>')
    h += ['</tbody>', '</table>']
    return '\n'.join(h)


def render_list(items) -> str:
    """items: (indent, text) pairs; indent 0 = top level, else nested."""
    h = ['<ul>']
    nested = None

    def close_nested():
        nonlocal nested
        if nested:
            h.append('<ul>'
                     + '\n'.join(f'<li>{render_inline(t)}</li>' for t in nested)
                     + '</ul>')
            nested = None

    for indent, text in items:
        if indent == 0:
            close_nested()
            h.append(f'<li>{render_inline(text)}')
        else:
            if nested is None:
                nested = []
            nested.append(text)
    close_nested()
    h.append('</ul>')
    return '\n'.join(h)


def render_md(md: str) -> str:
    """Markdown text (doc_maker's generated subset) -> HTML body."""
    lines = md.replace('\r\n', '\n').split('\n')
    out = []
    i, n = 0, len(lines)
    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith('```'):
            lang = stripped[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            cls = f' class="lang-{lang}"' if lang else ''
            pre = (f'<pre><code{cls}>'
                   f'{html.escape(chr(10).join(buf))}</code></pre>')
            # Two separate collapsible zones, both closed by default:
            # the source, and (when present) its "Call graph" list.
            j = i
            while j < n and not lines[j].strip():
                j += 1
            if j < n and lines[j].strip() == '**Call graph**':
                j += 1
                while j < n and not lines[j].strip():
                    j += 1
                items = []
                while j < n and lines[j].strip().startswith('- '):
                    raw = lines[j]
                    items.append((len(raw) - len(raw.lstrip()),
                                 raw.strip()[2:]))
                    j += 1
                if items:
                    out.append('<details class="src">'
                               '<summary>Source</summary>\n'
                               + pre + '\n</details>')
                    out.append('<details class="cg">'
                               '<summary>Call graph</summary>\n'
                               + render_list(items) + '\n</details>')
                    i = j
                    continue
            out.append('<details class="src"><summary>Source</summary>\n'
                       + pre + '\n</details>')
            continue
        m = _HEAD_RE.match(lines[i])
        if m:
            lvl = len(m.group(1))
            out.append(f'<h{lvl}>{render_inline(m.group(2))}</h{lvl}>')
            i += 1
            continue
        if _HR_RE.match(stripped):
            out.append('<hr>')
            i += 1
            continue
        if stripped.startswith('|'):
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append(lines[i])
                i += 1
            out.append(render_table(rows))
            continue
        if stripped.startswith('- '):
            items = []
            while i < n and lines[i].strip().startswith('- '):
                raw = lines[i]
                indent = len(raw) - len(raw.lstrip())
                items.append((indent, raw.strip()[2:]))
                i += 1
            out.append(render_list(items))
            continue
        # paragraph: until a blank line or another block start
        buf = [lines[i].strip()]
        i += 1
        while (i < n and lines[i].strip()
               and not lines[i].lstrip().startswith(('#', '```', '|', '- '))
               and not _HR_RE.match(lines[i].strip())):
            buf.append(lines[i].strip())
            i += 1
        out.append('<p>' + render_inline(' '.join(buf)) + '</p>')
    return '\n'.join(out)
