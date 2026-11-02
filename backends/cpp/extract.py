"""C / C++ / CUDA extraction: walk a tree-sitter tree into neutral records."""
import re

from backends._shared import _all_comments, _dev_comment, parse_llm_directive

from .calls import call_target
from .comments import comment_text
from .constants import CLASS_TYPES, LANG
from .includes import include_module
from .nodes import (
    declarator_name,
    definition_start_line,
    find_function_declarator,
    function_params,
    is_function_prototype,
    join_parts,
    name_parts,
    node_row,
    node_text,
    same_node,
)
from .parser import dialect, parser_for
from .pybind import bindings
from .values import classify_value, is_include_guard, value_text


def extract(source: str, relpath: str) -> dict:
    """Project one file's concrete syntax tree into the backend contract."""
    source = source.removeprefix('\ufeff')
    root = parser_for(relpath).parse(source.encode('utf-8')).root_node
    comments = _all_comments(root)
    pybind_bindings = bindings(root, relpath)
    lines = source.splitlines()
    fns, file_vars, calls, imports, classes = [], [], [], [], []
    seen_fn, seen_call, seen_var, seen_cls = set(), set(), set(), set()
    import_mods = []

    def add_fn(name, line, end_line, params, vararg, dev, qualified):
        fid = f'fn:{relpath}::{name}@{line}'
        if fid in seen_fn:
            return
        seen_fn.add(fid)
        a, b = line - 1, min(end_line, len(lines))
        body = '\n'.join(lines[a:b])
        dev, skip = parse_llm_directive(dev)
        rec = {'id': fid, 'name': name, 'qualified': qualified,
               'line': line, 'end_line': end_line,
               'params': list(params), 'vararg': bool(vararg),
               'body': body, 'developer_comment': dev}
        if skip:
            rec['skip_llm'] = True
        fns.append(rec)

    def add_class(name, qualified, line, end_line, dev=None):
        key = (name, line)
        if key in seen_cls:
            return
        seen_cls.add(key)
        dev, skip = parse_llm_directive(dev)
        rec = {'name': name, 'qualified': qualified,
               'line': line, 'end_line': end_line,
               'developer_comment': dev}
        if skip:
            rec['skip_llm'] = True
        classes.append(rec)

    def note_var(name, line, value, dev=None):
        if not name or name in seen_var:
            return
        seen_var.add(name)
        dev, skip = parse_llm_directive(dev)
        rec = {'name': name, 'line': line, 'init': classify_value(value),
               'developer_comment': dev}
        text = value_text(value)
        if text:
            rec['value'] = text
        if skip:
            rec['skip_llm'] = True
        file_vars.append(rec)

    def note_import(module, line):
        key = (module, line)
        if key not in import_mods:
            import_mods.append(key)
            imports.append({'module': module, 'line': line})

    def note_call(node, owner_qual):
        callee, method = call_target(node)
        # ``this->m()`` / ``this.m()``: bind the receiver to the enclosing
        # class so the graph can resolve it as Class.method.
        if callee == 'this' and method and owner_qual:
            callee = owner_qual
        line = node_row(node)
        key = (callee, method, line)
        if key in seen_call:
            return
        seen_call.add(key)
        calls.append({'callee': callee, 'line': line, 'method': method})

    def walk(node, qual=(), in_function=False, class_depth=0,
             owner_qual=None):
        t = node.type

        if t == 'comment':
            return

        if t == 'function_definition':
            name_node = None
            fd = find_function_declarator(
                node.child_by_field_name('declarator'))
            if fd is not None:
                name_node = fd.child_by_field_name('declarator')
            parts, absolute = name_parts(name_node)
            if parts:
                name = parts[-1]
                full = parts if absolute else join_parts(qual, parts)
                qualified = '.'.join(full)
                line = definition_start_line(node)
                end_line = node.end_point[0] + 1
                params, vararg = function_params(node)
                add_fn(name, line, end_line, params, vararg,
                       _dev_comment(comments, line, comment_text),
                       qualified)
                owner = '.'.join(full[:-1]) if len(full) > 1 else \
                    ('.'.join(qual) if qual else None)
                for c in node.children:
                    walk(c, qual, True, class_depth, owner)
                return
            # No name (anonymous construct): fall through to the generic
            # walk so calls in the body are still visible.
            for c in node.children:
                walk(c, qual, True, class_depth, owner_qual)
            return

        if t in CLASS_TYPES:
            name_node = node.child_by_field_name('name')
            body = node.child_by_field_name('body')
            if body is None:
                return  # forward declaration
            if name_node is not None:
                parts, _absolute = name_parts(name_node)
                name = parts[-1] if parts else node_text(name_node).strip()
                if name:
                    full = join_parts(qual, parts or (name,))
                    qualified = '.'.join(full)
                    line = definition_start_line(node)
                    add_class(name, qualified, line,
                              node.end_point[0] + 1,
                              _dev_comment(comments, line, comment_text))
                    for c in node.children:
                        if same_node(c, body):
                            walk(c, full, in_function, class_depth + 1,
                                 owner_qual)
                        else:
                            walk(c, qual, in_function, class_depth,
                                 owner_qual)
                    return
            # Anonymous class/struct: no class node, but methods inside still
            # belong to the current scope.
            for c in node.children:
                if same_node(c, body):
                    walk(c, qual, in_function, class_depth + 1, owner_qual)
                else:
                    walk(c, qual, in_function, class_depth, owner_qual)
            return

        if t == 'namespace_definition':
            name_node = node.child_by_field_name('name')
            body = node.child_by_field_name('body')
            parts = name_parts(name_node)[0] if name_node is not None else ()
            full = join_parts(qual, parts) if parts else qual
            if body is not None:
                walk(body, full, in_function, class_depth, owner_qual)
            return

        if t == 'linkage_specification':
            body = node.child_by_field_name('body')
            if body is not None:
                walk(body, qual, in_function, class_depth, owner_qual)
            return

        if t == 'preproc_include':
            module = include_module(node)
            if module:
                note_import(module, node_row(node))
            return

        if t == 'preproc_def':
            if not in_function and class_depth == 0:
                name_node = node.child_by_field_name('name')
                if name_node is not None:
                    name = node_text(name_node).strip()
                    value = node.child_by_field_name('value')
                    # Classify the raw replacement text (preproc_arg).
                    init = 'expr'
                    raw = node_text(value).strip() if value is not None else ''
                    if is_include_guard(name, raw):
                        return
                    if raw.startswith(('"', "'")):
                        init = 'string'
                    elif re.fullmatch(r'[-+]?(0[xX][0-9a-fA-F]+|\d+'
                                      r'(\.\d*)?([eE][-+]?\d+)?)[uUlLfF]*',
                                      raw):
                        init = 'number'
                    dev, skip = parse_llm_directive(
                        _dev_comment(comments, node_row(node), comment_text))
                    rec = {'name': name, 'line': node_row(node), 'init': init,
                           'developer_comment': dev}
                    if raw:
                        rec['value'] = raw[:400]
                    if skip:
                        rec['skip_llm'] = True
                    if name not in seen_var:
                        seen_var.add(name)
                        file_vars.append(rec)
            return

        if t == 'preproc_function_def':
            name_node = node.child_by_field_name('name')
            params_node = node.child_by_field_name('parameters')
            if name_node is not None:
                name = node_text(name_node).strip()
                params, vararg = [], False
                if params_node is not None:
                    for c in params_node.children:
                        if c.type == '...':
                            vararg = True
                        elif c.type == 'identifier':
                            params.append(node_text(c).strip())
                        elif c.type == 'variadic_parameter':
                            vararg = True
                line = node_row(node)
                end_line = node.end_point[0] + 1
                full = join_parts(qual, (name,))
                add_fn(name, line, end_line, params, vararg,
                       _dev_comment(comments, line, comment_text),
                       '.'.join(full))
            return

        if t == 'declaration':
            if not in_function and class_depth == 0:
                for d in node.children_by_field_name('declarator'):
                    if is_function_prototype(d):
                        continue
                    name = declarator_name(d)
                    value = d.child_by_field_name('value') \
                        if d.type == 'init_declarator' else None
                    if name:
                        note_var(name, node_row(node), value,
                                 _dev_comment(comments, node_row(node),
                                              comment_text))
            # Calls can live in initializers and default arguments; keep
            # walking even inside a function body.
            for c in node.children:
                walk(c, qual, in_function, class_depth, owner_qual)
            return

        if t == 'call_expression':
            note_call(node, owner_qual)
            # fall through: nested calls (foo(bar())) are visited too

        for c in node.children:
            walk(c, qual, in_function, class_depth, owner_qual)

    walk(root)
    return {'functions': fns, 'file_vars': file_vars,
            'calls': calls, 'imports': imports, 'classes': classes,
            'bindings': pybind_bindings,
            'lang': LANG, 'dialect': dialect(relpath, source)}
