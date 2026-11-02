"""Walk a tree-sitter-python tree into the neutral backend records."""
from backends._shared import _all_comments, _dev_comment, parse_llm_directive

from .comments import comment_text
from .nodes import (
    classify_value,
    dotted_parts,
    dotted_path,
    function_params,
    node_row,
    node_text,
)
from .parser import parser


def extract(source: str, relpath: str) -> dict:
    source = source.removeprefix('\ufeff')
    root = parser.parse(source.encode('utf-8')).root_node
    comments = _all_comments(root)
    lines = source.splitlines()
    fns, file_vars, calls, imports, classes = [], [], [], [], []
    seen_fn, seen_call, seen_var, seen_cls = set(), set(), set(), set()
    import_mods = []

    def add_fn(name, line, end_line, params, vararg, dev=None,
               qualified=None):
        fid = f'fn:{relpath}::{name}@{line}'
        if fid in seen_fn:
            return
        seen_fn.add(fid)
        a, b = line - 1, min(end_line, len(lines))
        body = '\n'.join(lines[a:b])
        dev, skip = parse_llm_directive(dev)
        rec = {'id': fid, 'name': name, 'qualified': qualified or name,
               'line': line, 'end_line': end_line,
               'params': list(params), 'vararg': bool(vararg),
               'body': body, 'developer_comment': dev}
        if skip:
            rec['skip_llm'] = True
        fns.append(rec)

    def note_call(node):
        fn = node.child_by_field_name('function')
        if fn is None:
            return
        name, method = None, None
        if fn.type == 'identifier':
            name = node_text(fn).strip() or None
        elif fn.type == 'attribute':
            method_node = fn.child_by_field_name('attribute')
            if method_node is None:  # older grammar field name
                method_node = fn.child_by_field_name('value')
            if method_node is not None:
                method = node_text(method_node)
                receiver = fn.child_by_field_name('object')
                if receiver is None:
                    receiver = fn.child_by_field_name('value')
                # A static dotted receiver is a resolvable target (e.g.
                # `deep.pack.mod` in `deep.pack.mod.launch(...)`); a dynamic
                # one (call / subscript / lambda) is not — keep the call
                # VISIBLE as external `?.method` rather than dropping it.
                parts = dotted_path(receiver)
                name = '.'.join(parts) if parts else None
            else:
                parts = dotted_path(fn)
                name = '.'.join(parts) if parts else None
        else:
            # `getattr(obj, 'x')()` and the like: the callee is itself a
            # computed expression — surface as external `?`.
            name, method = None, None
        line = node_row(node)
        key = (name, method, line)
        if key in seen_call:
            return
        seen_call.add(key)
        calls.append({'callee': name, 'line': line, 'method': method})

    def note_import(module, line, bind=None, name=None, level=0):
        key = (module, bind, name, level)
        if key not in import_mods:
            import_mods.append(key)
            rec = {'module': module, 'line': line, 'level': level}
            if bind:
                rec['bind'] = bind
            if name:
                rec['name'] = name
            imports.append(rec)

    def note_var(name, line, value, dev=None):
        if not name or name in seen_var:
            return
        seen_var.add(name)
        dev, skip = parse_llm_directive(dev)
        rec = {'name': name, 'line': line, 'init': classify_value(value),
               'developer_comment': dev}
        if value is not None:
            text = node_text(value).strip()
            if text:
                rec['value'] = text[:400]
        if skip:
            rec['skip_llm'] = True
        file_vars.append(rec)

    def record_function(fn_node, anchor_line, depth, qual):
        """Record a function/method and walk its parameters, return
        annotation and body so calls in defaults/annotations are not lost.

        ``anchor_line`` is where the developer comment is glued: the ``def``
        line for a plain function, the first decorator line for a decorated
        one. ``qual`` is the tuple of enclosing class names (innermost last).
        """
        nm = fn_node.child_by_field_name('name')
        if nm is not None:
            name = node_text(nm)
            params, vararg = function_params(fn_node)
            qualified = '.'.join(qual + (name,)) if qual else name
            add_fn(name, node_row(fn_node), fn_node.end_point[0] + 1,
                   params, vararg,
                   _dev_comment(comments, anchor_line, comment_text),
                   qualified)
        for field in ('parameters', 'return_type'):
            part = fn_node.child_by_field_name(field)
            if part is not None:
                walk(part, depth + 1, qual)
        body = fn_node.child_by_field_name('body')
        if body is not None:
            walk(body, depth + 1, qual)

    def record_class(cls_node, anchor_line, depth, qual):
        """Record a class and walk its body. ``anchor_line`` is the line a
        developer comment is glued against (the first decorator for a
        decorated class, otherwise the ``class`` line)."""
        nm = cls_node.child_by_field_name('name')
        cname = node_text(nm) if nm is not None else None
        if cname is not None:
            row = node_row(cls_node)
            key = (cname, row)
            if key not in seen_cls:
                seen_cls.add(key)
                dev, skip = parse_llm_directive(
                    _dev_comment(comments, anchor_line, comment_text))
                rec = {'name': cname,
                       'qualified': '.'.join(qual + (cname,))
                       if qual else cname,
                       'line': row,
                       'end_line': cls_node.end_point[0] + 1,
                       'developer_comment': dev}
                if skip:
                    rec['skip_llm'] = True
                classes.append(rec)
        # Base classes may contain calls (`class Foo(Base())`).
        sup = cls_node.child_by_field_name('superclasses')
        if sup is not None:
            walk(sup, depth, qual)
        # Body is a nested scope: class attributes are NOT module-level
        # file_vars, and methods get qualified names (``Vec3.normalize``).
        body = cls_node.child_by_field_name('body')
        if body is not None:
            q = qual + (cname,) if cname is not None else qual
            walk(body, depth + 1, q)

    def walk(node, depth, qual=()):
        t = node.type
        if t == 'function_definition':
            record_function(node, node_row(node), depth, qual)
            return

        if t == 'decorated_definition':
            fn_node = next((c for c in node.children
                            if c.type == 'function_definition'), None)
            if fn_node is not None:
                # Glue the developer comment against the FIRST decorator line
                # (the top of this block), not the def line.
                record_function(fn_node, node_row(node), depth, qual)
                return
            cls_node = next((c for c in node.children
                             if c.type == 'class_definition'), None)
            if cls_node is not None:
                record_class(cls_node, node_row(node), depth, qual)
                return
            # A decorated non-function falls through to the generic walk.

        if t == 'assignment' and depth == 0:
            left = node.child_by_field_name('left')
            value = node.child_by_field_name('right')
            if left is not None and left.type == 'identifier':
                note_var(node_text(left), node_row(node), value,
                         _dev_comment(comments, node_row(node),
                                      comment_text))
            for c in node.children:
                walk(c, depth, qual)
            return

        if t == 'annotated_assignment' and depth == 0:
            left = node.child_by_field_name('left')
            value = node.child_by_field_name('value')
            if left is not None and left.type == 'identifier':
                note_var(node_text(left), node_row(node), value,
                         _dev_comment(comments, node_row(node),
                                      comment_text))
            for c in node.children:
                walk(c, depth, qual)
            return

        if t == 'call':
            note_call(node)

        if t == 'import_statement':
            # `import a.b` -> dotted_name; `import a.b as x` -> aliased_import
            for c in node.children:
                if c.type == 'dotted_name':
                    parts = dotted_parts(c)
                    if parts:
                        note_import('.'.join(parts), node_row(node))
                elif c.type == 'aliased_import':
                    tgt = c.child_by_field_name('name')
                    al = c.child_by_field_name('alias')
                    parts = dotted_parts(tgt) if tgt is not None else None
                    if parts:
                        note_import('.'.join(parts), node_row(node),
                                    bind=node_text(al)
                                    if al is not None else None)
            return

        if t == 'import_from_statement':
            mod_node = node.child_by_field_name('module_name')
            level = 0
            module = None
            if mod_node is not None:
                if mod_node.type == 'relative_import':
                    prefix = mod_node.child_by_field_name('import_prefix')
                    if prefix is None:
                        for cc in mod_node.children:
                            if cc.type == 'import_prefix':
                                prefix = cc
                                break
                    level = len(node_text(prefix).strip()) if prefix else 1
                    modpart = mod_node.child_by_field_name('module')
                    if modpart is None:
                        for cc in mod_node.children:
                            if cc.type == 'dotted_name':
                                modpart = cc
                                break
                    if modpart is not None:
                        module = '.'.join(dotted_parts(modpart) or [])
                else:
                    parts = dotted_parts(mod_node)
                    if parts:
                        module = '.'.join(parts)
            line = node_row(node)
            # For a relative import, resolve the leading dots against the
            # importing file's directory so the graph can link to the real
            # file (e.g. `from .. import b` in pkg/sub/leaf.py -> pkg/b).
            base = ''
            if level > 0:
                parts = relpath.replace('\\', '/').split('/')
                base = parts[:-1]
                base = base[:len(base) - (level - 1)]
                base = '/'.join(base)

            def eff(target):
                if level == 0 or not target:
                    return target
                if base:
                    return base + '/' + target
                return target

            # Only symbols AFTER the `import` keyword are imported names; the
            # module path before `import` must be skipped, otherwise
            # `from m import n` also emits a PHANTOM import for `m`. The
            # grammar gives the module a `module_name` field, but tree-sitter
            # returns fresh wrappers per access, so position — not identity —
            # is the reliable way to tell the two dotted_names apart.
            children = list(node.children)
            import_idx = next((i for i, c in enumerate(children)
                               if c.type == 'import'), None)
            for i, c in enumerate(children):
                if import_idx is not None and i <= import_idx:
                    continue
                if c.type == 'dotted_name':
                    nm = '.'.join(dotted_parts(c) or [])
                    if not nm:
                        continue
                    target = eff(module) if module else eff(nm)
                    note_import(target, line, bind=nm, name=nm, level=level)
                elif c.type == 'aliased_import':
                    tgt = c.child_by_field_name('name')
                    al = c.child_by_field_name('alias')
                    tp = dotted_parts(tgt) if tgt is not None else None
                    if not tp:
                        continue
                    name = '.'.join(tp)
                    bind = node_text(al) if al is not None else name
                    target = eff(module) if module else eff(name)
                    note_import(target, line, bind=bind, name=name,
                                level=level)
                elif c.type == 'wildcard_import':
                    target = eff(module) if module else \
                        (base if level else None)
                    if target:
                        note_import(target, line, bind='*', name=None,
                                    level=level)
            return

        if t == 'class_definition':
            # Classes are resolvable symbols: constructor calls must bind
            # through the caller's imports instead of falling through to
            # `external`.
            record_class(node, node_row(node), depth, qual)
            return

        for c in node.children:
            walk(c, depth, qual)

    walk(root, 0)
    return {'functions': fns, 'file_vars': file_vars,
            'calls': calls, 'imports': imports, 'classes': classes}
