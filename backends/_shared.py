"""Shared comment-glue helpers for backends.

A neutral module (no imports from the ``backends`` package) so backend
packages can import these without a circular dependency on the registry.

The ``developer_comment`` contract (see backend_design.md):

Glue rule (identical for every language):

- A comment node is *glued* to a function when its **last line is exactly
  the line above the function's first line** (no blank line or other code
  between them).
- The block is the **maximal run**: keep extending upward while the
  previous comment's last line sits exactly on the line above the current
  top.
- Any other content between comment and function (code, blank line) breaks
  the glue → ``None``.

Backends supply a per-language ``clean(node)`` that strips the comment
markers (e.g. Lua ``comment_content``, Python leading ``#``+space).
"""


def _all_comments(root, types=('comment',)):
    """Comment nodes of ``root`` in document order."""
    out = []

    def w(n):
        if n.type in types:
            out.append(n)
        else:
            for c in n.children:
                w(c)

    w(root)
    return out


def _dev_comment(comments, fn_line, clean):
    """Text of the comment block glued directly above 1-based line
    ``fn_line``, or None.

    The block is the maximal run of comments whose last line sits exactly
    on the line immediately above the function (and above each other);
    any other content or a blank line between comment and function breaks
    the glue. ``clean`` maps one comment node to its cleaned text.
    """
    run = []
    top = fn_line
    while True:
        hit = next((c for c in comments if c.end_point[0] + 1 == top - 1),
                   None)
        if hit is None:
            break
        run.insert(0, hit)
        top = hit.start_point[0] + 1
    if not run:
        return None
    text = '\n'.join(clean(c) for c in run).strip()
    return text or None
