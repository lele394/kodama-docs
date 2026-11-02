"""C / C++ / CUDA extraction backend (tree-sitter based).

Parsing is delegated to the official tree-sitter-cpp grammar for C and C++,
and to tree-sitter-cuda for ``.cu`` / ``.cuh`` files.  This module only walks
the concrete syntax tree and projects it into the common shape documented in
``backends/backend_design.md``.  No hand-rolled tokenizer or parser.

Policy decisions (kept intentionally simple and deterministic):

* **Definitions, not prototypes.**  A header prototype (``int f(int);``) is
  not a symbol record; the definition in the ``.c`` / ``.cpp`` file is.  This
  avoids documenting the same function twice.  Header-only/inline/template
  definitions are still ``function_definition`` nodes and are recorded.
* **Function-like macros are functions.**  ``#define ADD(a, b) ...`` is
  recorded with the macro's parameters so C APIs built on macros are visible.
  Object-like macros (``#define MAX 100``) are file variables.
* **Qualified names are dotted.**  ``ns::Engine::step`` becomes
  ``ns.Engine.step`` — the graph resolver already splits on ``.``.
* **Quoted includes only.**  ``#include "foo.h"`` is an import; angle-bracket
  includes (``<vector>``, ``<cuda_runtime.h>``) are system headers and are
  skipped so they do not become thousands of unresolved module nodes.
* **CUDA kernel launches are calls.**  ``k<<<grid, block>>>(args)`` is a
  normal ``call_expression`` in tree-sitter-cuda, so it shows up in the call
  graph without special handling.  ``__global__`` / ``__device__`` etc. are
  left in the body; the prose prompt sees them.

Known limitations: tree-sitter is syntactic, so overload resolution, macro
expansion, template instantiation and include-directory resolution are best
effort.  Calls are resolved by the graph's name/qualified-name heuristics,
never guessed here.
"""
import os
import re

import tree_sitter_cpp as tscpp
import tree_sitter_cuda as tscuda
from tree_sitter import Language, Parser

from backends._shared import _all_comments, _dev_comment, parse_llm_directive

#: Shared by C, C++ and CUDA so the graph may link across the C family
#: (a C++ file calling a C function is a real edge).  ``dialect`` below keeps
#: the finer distinction for display/diagnostics.
LANG = 'c-family'

_CPP_PARSER = Parser(Language(tscpp.language()))
_CUDA_PARSER = Parser(Language(tscuda.language()))

_CUDA_EXTS = ('.cu', '.cuh')

#: Names that are not project symbols.  C/C++ standard library, common libc,
#: and the CUDA runtime + device builtins.  ``std`` covers every ``std::...``
#: call through the graph's namespace handling.
BUILTIN_NAMES = {
    # C / C++ keywords that can appear in callee position
    'NULL', 'nullptr', 'true', 'false', 'this', 'void', 'sizeof',
    # common libc
    'printf', 'fprintf', 'sprintf', 'snprintf', 'vprintf', 'vfprintf',
    'scanf', 'sscanf', 'puts', 'putchar', 'getchar', 'perror',
    'malloc', 'calloc', 'realloc', 'free', 'memcpy', 'memmove', 'memset',
    'memcmp', 'strlen', 'strcmp', 'strncmp', 'strcpy', 'strncpy', 'strcat',
    'strncat', 'strchr', 'strrchr', 'strstr', 'strtok', 'strerror',
    'atoi', 'atol', 'atoll', 'atof', 'strtol', 'strtoul', 'strtod',
    'abs', 'labs', 'llabs', 'fabs', 'fabsf', 'sqrt', 'sqrtf', 'pow',
    'powf', 'sin', 'sinf', 'cos', 'cosf', 'tan', 'tanf', 'exp', 'expf',
    'log', 'logf', 'log2', 'log10', 'floor', 'floorf', 'ceil', 'ceilf',
    'round', 'roundf', 'trunc', 'fmod', 'fmodf', 'fma', 'fmaf',
    'rand', 'srand', 'time', 'clock', 'getenv', 'exit', 'abort', 'assert',
    'fopen', 'fclose', 'fread', 'fwrite', 'fflush', 'fseek', 'ftell',
    'fgets', 'fputs', 'open', 'close', 'read', 'write',
    # C++ std namespace (base name; std::foo is handled as a namespace)
    'std',
    # CUDA runtime / driver API
    'cudaMalloc', 'cudaMallocManaged', 'cudaMallocHost', 'cudaHostAlloc',
    'cudaFree', 'cudaFreeHost', 'cudaMemcpy', 'cudaMemcpyAsync',
    'cudaMemset', 'cudaMemsetAsync', 'cudaDeviceSynchronize',
    'cudaStreamSynchronize', 'cudaStreamCreate', 'cudaStreamDestroy',
    'cudaStreamWaitEvent', 'cudaEventCreate', 'cudaEventDestroy',
    'cudaEventRecord', 'cudaEventSynchronize', 'cudaEventElapsedTime',
    'cudaGetLastError', 'cudaPeekAtLastError', 'cudaGetDeviceCount',
    'cudaGetDeviceProperties', 'cudaSetDevice', 'cudaGetDevice',
    'cudaDeviceReset', 'cudaMemGetInfo', 'cudaHostGetDevicePointer',
    # CUDA device builtins
    '__syncthreads', '__syncwarp', '__threadfence', '__threadfence_block',
    '__shfl_down_sync', '__shfl_up_sync', '__shfl_xor_sync', '__shfl_sync',
    'atomicAdd', 'atomicSub', 'atomicExch', 'atomicMin', 'atomicMax',
    'atomicInc', 'atomicDec', 'atomicCAS', 'atomicAnd', 'atomicOr',
    'atomicXor',
    'threadIdx', 'blockIdx', 'blockDim', 'gridDim', 'warpSize',
    'rsqrtf', '__fdividef', '__expf', '__logf', '__log2f', '__sinf',
    '__cosf', '__tanf', '__powf', '__saturatef',
}

_IDENT_TYPES = {
    'identifier', 'field_identifier', 'namespace_identifier',
    'type_identifier', 'statement_identifier',
}

_CLASS_TYPES = ('class_specifier', 'struct_specifier', 'union_specifier')

#: Common include-guard macro names (``FOO_H``, ``FOO_HPP``, ``__FOO_H__``).
#: They are file plumbing, not API constants, so they are not documented as
#: file variables — otherwise every header would create a pointless LLM task.
_GUARD_RE = re.compile(
    r'^_*[A-Z][A-Z0-9_]*_(H|HH|HPP|HXX|CUH|INCLUDED)_*$')


def _is_include_guard(name, value_text):
    if not _GUARD_RE.match(name):
        return False
    return value_text.strip() in ('', '1', '1U', '1UL', '1ULL')


def _row(node):
    return node.start_point[0] + 1


def _text(node):
    return node.text.decode('utf-8')


def _same_node(a, b):
    """tree-sitter may hand out fresh wrappers for the same node — compare
    source ranges, not object identity."""
    return a is not None and b is not None and \
        a.start_byte == b.start_byte and a.end_byte == b.end_byte


def _parser_for(relpath):
    return _CUDA_PARSER if \
        os.path.splitext(relpath)[1].lower() in _CUDA_EXTS else _CPP_PARSER


def _dialect(relpath, source=''):
    ext = os.path.splitext(relpath)[1].lower()
    if ext in _CUDA_EXTS:
        return 'cuda'
    if ext == '.c':
        return 'c'
    if ext == '.h':
        # .h is ambiguous. C++-only constructs are a strong signal; plain
        # extern "C" headers stay C.
        if re.search(r'\b(class|namespace|template|public|private|'
                     r'protected)\b|::|\bstd\b', source):
            return 'cpp'
        return 'c'
    return 'cpp'


def _comment_text(node):
    """Strip ``//``, ``/* */`` and leading ``*`` decorations."""
    t = _text(node).strip()
    if t.startswith('//'):
        t = t[2:]
        t = t.lstrip('/!<')
        return t.strip()
    if t.startswith('/*'):
        t = t[2:].removesuffix('*/')
        t = t.lstrip('!<')
        out = []
        for line in t.splitlines():
            line = line.strip()
            line = re.sub(r'^\*\s?', '', line)
            out.append(line)
        return '\n'.join(out).strip()
    return t


def _name_parts(node):
    """(path parts, absolute) for a name/declarator node.

    ``ns::Engine::run`` -> (('ns', 'Engine', 'run'), False);
    ``::foo`` -> (('foo',), True); ``foo`` -> (('foo',), False).
    """
    if node is None:
        return (), False
    t = node.type
    if t in _IDENT_TYPES:
        s = _text(node).strip()
        return ((s,) if s else ()), False
    if t in ('destructor_name', 'operator_name'):
        s = _text(node).strip()
        return ((s,) if s else ()), False
    if t == 'nested_namespace_specifier':
        raw = _text(node).replace('::', '.')
        return tuple(p for p in raw.split('.') if p), False
    if t == 'qualified_identifier':
        absolute = _text(node).lstrip().startswith('::')
        scope = node.child_by_field_name('scope')
        name = node.child_by_field_name('name')
        sp = _name_parts(scope)[0] if scope is not None else ()
        np = _name_parts(name)[0] if name is not None else ()
        if not np:
            raw = _text(node).replace('::', '.').strip('.')
            return tuple(p for p in raw.split('.') if p), absolute
        return tuple(sp) + tuple(np), absolute
    if t in ('template_function', 'template_method', 'template_type'):
        name = node.child_by_field_name('name')
        if name is not None:
            return _name_parts(name)
        raw = _text(node).split('<', 1)[0]
        return ((raw.strip(),) if raw.strip() else ()), False
    if t in ('pointer_declarator', 'reference_declarator',
             'parenthesized_declarator', 'function_declarator',
             'array_declarator', 'init_declarator'):
        d = node.child_by_field_name('declarator')
        if d is not None:
            return _name_parts(d)
    for c in node.children:
        if c.type in _IDENT_TYPES or c.type in ('destructor_name',
                                                 'operator_name'):
            return _name_parts(c)
    return (), False


def _join_parts(qual, parts):
    """Prefix ``parts`` with the current lexical scope, without duplicating
    a scope the name already spells out (``mixed::Engine::run`` inside
    ``namespace mixed``)."""
    qual = tuple(p for p in qual if p)
    parts = tuple(p for p in parts if p)
    if not parts:
        return qual
    if qual and parts[:len(qual)] == qual:
        return parts
    return qual + parts


def _def_start_line(node):
    """Line where the definition starts, including a leading ``template``
    line so the body slice and developer-comment glue cover the whole
    construct."""
    while node.parent is not None and node.parent.type == 'template_declaration':
        node = node.parent
    return _row(node)


def _find_function_declarator(node):
    if node is None:
        return None
    if node.type == 'function_declarator':
        return node
    for c in node.children:
        hit = _find_function_declarator(c)
        if hit is not None:
            return hit
    return None


def _declarator_name(node):
    """The identifier introduced by a declarator, descending through
    pointers/references/arrays/function-pointer parentheses."""
    if node is None:
        return None
    t = node.type
    if t in ('identifier', 'field_identifier', 'type_identifier'):
        return _text(node).strip() or None
    if t in ('destructor_name', 'operator_name'):
        return _text(node).strip() or None
    if t in ('pointer_declarator', 'reference_declarator',
             'array_declarator', 'parenthesized_declarator',
             'function_declarator', 'init_declarator',
             'attributed_declarator', 'parameter_pack'):
        d = node.child_by_field_name('declarator')
        if d is not None:
            return _declarator_name(d)
        for c in node.children:
            name = _declarator_name(c)
            if name:
                return name
    return None


def _is_function_prototype(declarator):
    """True for ``int f(int);`` and false for a function-pointer variable
    ``int (*fp)(int);``."""
    if declarator is None or declarator.type != 'function_declarator':
        return False
    inner = declarator.child_by_field_name('declarator')
    return inner is not None and inner.type in (
        'identifier', 'field_identifier', 'qualified_identifier',
        'destructor_name', 'operator_name', 'template_function')


def _params(fn_node):
    """(parameter names, vararg) for a function definition."""
    decl = _find_function_declarator(fn_node.child_by_field_name('declarator'))
    plist = decl.child_by_field_name('parameters') \
        if decl is not None else None
    if plist is None:
        return [], False
    names, vararg = [], False
    for c in plist.children:
        if c.type == '...':
            vararg = True
            continue
        if c.type not in ('parameter_declaration',
                          'optional_parameter_declaration',
                          'variadic_parameter', 'parameter_pack'):
            continue
        if c.type == 'variadic_parameter':
            vararg = True
            continue
        name = _declarator_name(c.child_by_field_name('declarator'))
        if name and name != 'void':
            names.append(name)
        # A parameter pack ``Ts...`` is variadic even without a ``...`` token.
        if _text(c).rstrip().endswith('...'):
            vararg = True
    return names, vararg


def _classify(value):
    if value is None:
        return 'empty'
    t = value.type
    if t in ('string_literal', 'raw_string_literal', 'concatenated_string'):
        return 'string'
    if t in ('number_literal', 'char_literal'):
        return 'number'
    if t in ('initializer_list', 'compound_literal_expression'):
        return 'table'
    if t in ('call_expression', 'new_expression'):
        return 'call'
    if t == 'lambda_expression':
        return 'function'
    return 'expr'


def _value_text(value):
    if value is None:
        return None
    text = _text(value).strip()
    return text[:400] if text else None


def _static_path(node):
    """Dotted path of a static receiver, or None when it is computed."""
    if node is None:
        return None
    t = node.type
    if t in ('identifier', 'this'):
        return _text(node).strip() or None
    if t == 'qualified_identifier':
        parts, _abs = _name_parts(node)
        return '.'.join(parts) if parts else None
    if t == 'field_expression':
        arg = node.child_by_field_name('argument')
        field = node.child_by_field_name('field')
        base = _static_path(arg)
        fld = _static_path(field) if field is not None else None
        if base and fld:
            return f'{base}.{fld}'
        return base or fld
    if t in ('template_function', 'template_method', 'template_type'):
        parts, _abs = _name_parts(node)
        return '.'.join(parts) if parts else None
    if t in ('pointer_expression', 'parenthesized_expression',
             'subscript_expression', 'call_expression'):
        return None
    return None


def _call_target(node):
    """(callee, method) for a call_expression, or (None, None) when dynamic."""
    fn = node.child_by_field_name('function')
    if fn is None:
        return None, None
    t = fn.type
    if t == 'identifier':
        return _text(fn).strip() or None, None
    if t == 'field_expression':
        field = fn.child_by_field_name('field')
        arg = fn.child_by_field_name('argument')
        method = None
        if field is not None:
            if field.type in ('field_identifier', 'identifier'):
                method = _text(field).strip()
            else:
                parts, _abs = _name_parts(field)
                method = parts[-1] if parts else None
        receiver = _static_path(arg)
        return receiver, method
    if t == 'qualified_identifier':
        parts, _abs = _name_parts(fn)
        return ('.'.join(parts) if parts else None), None
    if t in ('template_function', 'template_method'):
        parts, _abs = _name_parts(fn)
        return ('.'.join(parts) if parts else None), None
    # ``(*fp)(...)``, ``arr[i](...)`` and other computed callees: keep the
    # call visible as an external ``?`` reference rather than guessing.
    return None, None


def _include_module(node):
    path = node.child_by_field_name('path')
    if path is None:
        return None
    if path.type != 'string_literal':
        return None  # angle-bracket system include
    raw = _text(path).strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    return None


# ----------------------------------------------------------------- pybind11
# A pybind11 module is the one place where a Python name is explicitly
# declared to be a C++ symbol.  Reading those declarations is deterministic
# (no guessing): the backend records them, and graph.py turns them into
# EXPORTS/BRIDGES edges and resolves `mixed_native.Engine`-style calls.

_BINDING_MODULE_MACROS = {'PYBIND11_MODULE', 'PYBIND11_EMBEDDED_MODULE'}
_PYBIND_DEF_FIELDS = {
    'def', 'def_static', 'def_readwrite', 'def_readonly',
    'def_property', 'def_property_readonly', 'def_property_readonly_static',
}


def _walk_nodes(node, types):
    """Yield descendants of ``node`` whose type is in ``types``."""
    if node.type in types:
        yield node
    for c in node.children:
        yield from _walk_nodes(c, types)


def _function_name(node):
    fd = _find_function_declarator(node.child_by_field_name('declarator'))
    if fd is None:
        return None
    parts, _abs = _name_parts(fd.child_by_field_name('declarator'))
    return parts[-1] if parts else None


def _string_value(node):
    if node is None or node.type != 'string_literal':
        return None
    raw = _text(node).strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    return None


def _cpp_ref(node):
    """C++ target of a pybind11 argument: ``&py_add`` / ``&ns::Engine::step``."""
    if node is None:
        return None
    if node.type == 'pointer_expression':
        return _cpp_ref(node.child_by_field_name('argument'))
    if node.type in ('identifier', 'qualified_identifier', 'template_function'):
        parts, _abs = _name_parts(node)
        return '.'.join(parts) if parts else None
    if node.type == 'parenthesized_expression':
        for c in node.children:
            hit = _cpp_ref(c)
            if hit:
                return hit
    return None


def _binding_receiver(call):
    """Walk a chained ``.def(...)`` call down to its base receiver.

    ``m.def(...)`` -> the ``m`` identifier.
    ``py::class_<T>(m, "T").def(...).def(...)`` -> the ``py::class_`` call.
    """
    cur = call
    while True:
        fn = cur.child_by_field_name('function')
        if fn is None or fn.type != 'field_expression':
            return cur
        arg = fn.child_by_field_name('argument')
        if arg is None:
            return cur
        if arg.type != 'call_expression':
            return arg
        afn = arg.child_by_field_name('function')
        if afn is not None and afn.type == 'field_expression':
            fld = afn.child_by_field_name('field')
            if fld is not None and _text(fld) in _PYBIND_DEF_FIELDS:
                cur = arg
                continue
        return arg


def _pybind_class_export(call):
    """(cpp_type, python_name) for ``py::class_<T>(m, "Name")``, else None."""
    fn = call.child_by_field_name('function')
    if fn is None or fn.type != 'qualified_identifier':
        return None
    name = fn.child_by_field_name('name')
    if name is None or name.type != 'template_function':
        return None
    base = name.child_by_field_name('name')
    if base is None or _text(base) not in ('class_', 'struct_'):
        return None
    args = name.child_by_field_name('arguments')
    cpp_type = None
    if args is not None:
        for c in args.children:
            if c.type == 'type_descriptor':
                t = c.child_by_field_name('type')
                if t is None and c.children:
                    t = c.children[0]
                parts, _abs = _name_parts(t)
                if parts:
                    cpp_type = '.'.join(parts)
                break
    py_name = None
    for a in _pybind_args(call):
        s = _string_value(a)
        if s:
            py_name = s
            break
    if cpp_type and py_name:
        return cpp_type, py_name
    return None


def _pybind_args(call):
    args = call.child_by_field_name('arguments')
    if args is None:
        return []
    return [c for c in args.children
            if c.type not in ('(', ')', ',')]


def _pybind_module_params(node):
    """(module name, module object) from ``PYBIND11_MODULE(name, m)``."""
    fd = _find_function_declarator(node.child_by_field_name('declarator'))
    plist = fd.child_by_field_name('parameters') \
        if fd is not None else None
    if plist is None:
        return None, None
    vals = [_text(c).strip() for c in plist.children
            if c.type in ('parameter_declaration',
                          'optional_parameter_declaration')]
    if len(vals) < 2:
        return None, None
    return vals[0].strip('"\''), vals[1]


def _pybind_bindings(root, relpath):
    """Explicit pybind11 exports declared in this file."""
    out = []
    seen = set()

    def add(kind, module, name, target, line, owner=None):
        key = (kind, module, name, target, owner)
        if key in seen:
            return
        seen.add(key)
        rec = {'kind': kind, 'module': module, 'name': name,
               'target': target, 'line': line}
        if owner:
            rec['owner'] = owner
        out.append(rec)

    for fn_node in _walk_nodes(root, ('function_definition',)):
        if _function_name(fn_node) not in _BINDING_MODULE_MACROS:
            continue
        module, module_var = _pybind_module_params(fn_node)
        body = fn_node.child_by_field_name('body')
        if not module or not module_var or body is None:
            continue
        for call in _walk_nodes(body, ('call_expression',)):
            fn = call.child_by_field_name('function')
            if fn is None or fn.type != 'field_expression':
                continue
            fld = fn.child_by_field_name('field')
            if fld is None or _text(fld) not in _PYBIND_DEF_FIELDS:
                continue
            args = _pybind_args(call)
            py_name = _string_value(args[0]) if args else None
            target = _cpp_ref(args[1]) if len(args) > 1 else None
            if not py_name or not target:
                continue
            base = _binding_receiver(call)
            cls = _pybind_class_export(base) \
                if base.type == 'call_expression' else None
            def_line = _row(fld)
            if cls is not None:
                cpp_type, py_cls = cls
                add('class', module, py_cls, cpp_type,
                    base.start_point[0] + 1)
                add('method', module, py_name, target,
                    def_line, owner=py_cls)
            elif base.type == 'identifier' and \
                    _text(base).strip() == module_var:
                add('function', module, py_name, target, def_line)
    return out


def extract(source: str, relpath: str) -> dict:
    source = source.removeprefix('\ufeff')
    root = _parser_for(relpath).parse(source.encode('utf-8')).root_node
    comments = _all_comments(root)
    bindings = _pybind_bindings(root, relpath)
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
        rec = {'name': name, 'line': line, 'init': _classify(value),
               'developer_comment': dev}
        text = _value_text(value)
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
        callee, method = _call_target(node)
        # ``this->m()`` / ``this.m()``: bind the receiver to the enclosing
        # class so the graph can resolve it as Class.method.
        if callee == 'this' and method and owner_qual:
            callee = owner_qual
        line = _row(node)
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
            fd = _find_function_declarator(
                node.child_by_field_name('declarator'))
            if fd is not None:
                name_node = fd.child_by_field_name('declarator')
            parts, absolute = _name_parts(name_node)
            if parts:
                name = parts[-1]
                full = parts if absolute else _join_parts(qual, parts)
                qualified = '.'.join(full)
                line = _def_start_line(node)
                end_line = node.end_point[0] + 1
                params, vararg = _params(node)
                add_fn(name, line, end_line, params, vararg,
                       _dev_comment(comments, line, _comment_text),
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

        if t in _CLASS_TYPES:
            name_node = node.child_by_field_name('name')
            body = node.child_by_field_name('body')
            if body is None:
                return  # forward declaration
            if name_node is not None:
                parts, _absolute = _name_parts(name_node)
                name = parts[-1] if parts else _text(name_node).strip()
                if name:
                    full = _join_parts(qual, parts or (name,))
                    qualified = '.'.join(full)
                    line = _def_start_line(node)
                    add_class(name, qualified, line,
                              node.end_point[0] + 1,
                              _dev_comment(comments, line, _comment_text))
                    for c in node.children:
                        if _same_node(c, body):
                            walk(c, full, in_function, class_depth + 1,
                                 owner_qual)
                        else:
                            walk(c, qual, in_function, class_depth,
                                 owner_qual)
                    return
            # Anonymous class/struct: no class node, but methods inside still
            # belong to the current scope.
            for c in node.children:
                if _same_node(c, body):
                    walk(c, qual, in_function, class_depth + 1, owner_qual)
                else:
                    walk(c, qual, in_function, class_depth, owner_qual)
            return

        if t == 'namespace_definition':
            name_node = node.child_by_field_name('name')
            body = node.child_by_field_name('body')
            parts = _name_parts(name_node)[0] if name_node is not None else ()
            full = _join_parts(qual, parts) if parts else qual
            if body is not None:
                walk(body, full, in_function, class_depth, owner_qual)
            return

        if t == 'linkage_specification':
            body = node.child_by_field_name('body')
            if body is not None:
                walk(body, qual, in_function, class_depth, owner_qual)
            return

        if t == 'preproc_include':
            module = _include_module(node)
            if module:
                note_import(module, _row(node))
            return

        if t == 'preproc_def':
            if not in_function and class_depth == 0:
                name_node = node.child_by_field_name('name')
                if name_node is not None:
                    name = _text(name_node).strip()
                    value = node.child_by_field_name('value')
                    # Classify the raw replacement text (preproc_arg).
                    init = 'expr'
                    raw = _text(value).strip() if value is not None else ''
                    if _is_include_guard(name, raw):
                        return
                    if raw.startswith(('"', "'")):
                        init = 'string'
                    elif re.fullmatch(r'[-+]?(0[xX][0-9a-fA-F]+|\d+'
                                      r'(\.\d*)?([eE][-+]?\d+)?)[uUlLfF]*',
                                      raw):
                        init = 'number'
                    dev, skip = parse_llm_directive(
                        _dev_comment(comments, _row(node), _comment_text))
                    rec = {'name': name, 'line': _row(node), 'init': init,
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
                name = _text(name_node).strip()
                params, vararg = [], False
                if params_node is not None:
                    for c in params_node.children:
                        if c.type == '...':
                            vararg = True
                        elif c.type == 'identifier':
                            params.append(_text(c).strip())
                        elif c.type == 'variadic_parameter':
                            vararg = True
                line = _row(node)
                end_line = node.end_point[0] + 1
                full = _join_parts(qual, (name,))
                add_fn(name, line, end_line, params, vararg,
                       _dev_comment(comments, line, _comment_text),
                       '.'.join(full))
            return

        if t == 'declaration':
            if not in_function and class_depth == 0:
                for d in node.children_by_field_name('declarator'):
                    if _is_function_prototype(d):
                        continue
                    name = _declarator_name(d)
                    value = d.child_by_field_name('value') \
                        if d.type == 'init_declarator' else None
                    if name:
                        note_var(name, _row(node), value,
                                 _dev_comment(comments, _row(node),
                                              _comment_text))
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
            'bindings': bindings,
            'lang': LANG, 'dialect': _dialect(relpath, source)}


def module_candidates(module, relpath):
    """Relpaths a quoted ``#include`` could resolve to.

    Tries the including file's directory first (the C/C++ convention), then
    the source root, then a common ``include/`` prefix.  The graph picks the
    first candidate that is a real project file; unresolved includes stay
    visible as ``mod:...`` nodes.
    """
    m = str(module or '').replace('\\', '/').strip()
    if not m or m.startswith('<'):
        return []
    d = os.path.dirname(str(relpath).replace('\\', '/'))
    out = []
    for base in (d, ''):
        p = os.path.normpath(os.path.join(base, m)).replace('\\', '/')
        while p.startswith('./'):
            p = p[2:]
        if p and p not in out:
            out.append(p)
    extra = os.path.normpath(os.path.join('include', m)).replace('\\', '/')
    if extra not in out:
        out.append(extra)
    return out
