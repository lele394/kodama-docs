"""Bundle web/ ES modules into one classic (non-module) script.

Why: the static site must work when it is opened straight from disk
(file://), and browsers refuse to load *external* ES modules there
("Module source URI is not allowed in this document"). So the static
build emits each UI entry point (sidebar.js, graph.js) as a single
self-contained classic script: every module it imports is inlined, and
imports/exports are rewritten onto a tiny define/require registry that
works everywhere, file:// included. The sources in web/ stay ES modules
(unchanged for the server, which serves them natively over http).

Only the ES-module subset the web/ sources actually use is supported;
anything else raises instead of emitting silently broken JS:

    import { a, b as c } from './x.js';
    export function name() {...}
    export const|let|var name = ...
    export { a, b };

(no default imports, no re-exports, no dynamic import(), no import.meta —
the parser below rejects them loudly, so adding such syntax to web/
breaks the static build until this file is extended)
"""
import os
import posixpath
import re

# import { a, b as c } from './x.js';   (the braces may span lines)
_IMPORT_RE = re.compile(
    r"import[ \t\n]*\{([^}]*)\}[ \t\n]*from[ \t\n]*['\"]([^'\"]+)['\"]\s*;")
# export function|const|let|var name
_EXPORT_DECL_RE = re.compile(
    r"^([ \t]*)export[ \t]+(function\*?|const|let|var)[ \t]+"
    r"([A-Za-z0-9_$]+)", re.M)
# export { a, b };
_EXPORT_LIST_RE = re.compile(
    r"^[ \t]*export[ \t]*\{([^}]*)\}[ \t]*;", re.M)


_IDENT_RE = re.compile(r'^[A-Za-z_$][A-Za-z0-9_$]*$')


def _names(spec_text: str):
    """'a, b as c' -> [('a', None), ('b', 'c')]  (local, alias)"""
    # comments inside the braces are legal JS: drop them before splitting
    spec_text = re.sub(r'/\*.*?\*/', '', spec_text, flags=re.S)
    spec_text = re.sub(r'//[^\n]*', '', spec_text)
    out = []
    for part in spec_text.split(','):
        part = part.strip()
        if not part:
            continue
        if ' as ' in part:
            local, alias = [p.strip() for p in part.split(' as ', 1)]
        else:
            local = alias = part
        if not _IDENT_RE.match(local):
            raise ValueError('unparseable import/export name: %r' % part)
        out.append((local, alias))
    return out


def parse_module(source: str) -> dict:
    """(imports, exports, spans) for the supported subset.

    imports: [(spec, [(local, alias), ...])] in source order
    exports: [(exported, local)] in source order
    spans:   all matched import/export regions (to catch strays)
    """
    imports = [(m.group(2), _names(m.group(1))) for m in _IMPORT_RE.finditer(source)]
    spans = [m.span() for rx in (_IMPORT_RE, _EXPORT_DECL_RE, _EXPORT_LIST_RE)
             for m in rx.finditer(source)]

    exports = []
    for m in _EXPORT_DECL_RE.finditer(source):
        exports.append((m.start(), (m.group(3), m.group(3))))
    for m in _EXPORT_LIST_RE.finditer(source):
        for local, alias in _names(m.group(1)):
            exports.append((m.start(), (alias if alias else local, local)))
    exports = [pair for _pos, pair in sorted(exports)]

    # any import/export token outside the matched regions is unsupported
    for word in ('import', 'export'):
        for m in re.finditer(r'\b' + word + r'\b', source):
            if not any(s <= m.start() < e for s, e in spans):
                raise ValueError(
                    'unsupported %r syntax in bundled JS (extend '
                    'kodama_docs/js_bundle.py first)' % word)
    return {'imports': imports, 'exports': exports}


def _resolve(mid: str, spec: str) -> str:
    if not (spec.startswith('./') or spec.startswith('../')):
        raise ValueError('only relative imports can be bundled: %r' % spec)
    return posixpath.normpath(posixpath.join(posixpath.dirname(mid), spec))


def bundle(webdir: str, entry: str) -> str:
    """Bundle webdir/entry (web/-relative, e.g. 'sidebar.js') plus its
    transitive relative imports into one classic-script string.

    Raises ValueError on cycles, missing files, or unsupported syntax."""
    def read(mid: str) -> str:
        path = os.path.join(webdir, *mid.split('/'))
        if not os.path.isfile(path):
            raise ValueError('bundled module not found: %s' % mid)
        with open(path, 'r', encoding='utf-8') as fh:
            return fh.read()

    modules = {}
    order = []
    done, visiting = set(), set()

    def visit(mid: str):
        if mid in done:
            return
        if mid in visiting:
            raise ValueError('import cycle at %s' % mid)
        visiting.add(mid)
        source = read(mid)
        mod = parse_module(source)
        for spec, _names_ in mod['imports']:
            visit(_resolve(mid, spec))
        visiting.discard(mid)
        modules[mid] = (source, mod)
        order.append(mid)
        done.add(mid)

    visit(entry)

    def transform(mid: str) -> str:
        source, mod = modules[mid]
        by_spec = {spec: names for spec, names in mod['imports']}

        def imp_repl(m):
            dep = _resolve(mid, m.group(2))
            # destructuring renames use ':' (unlike import's 'as')
            parts = [local + (': ' + alias if alias and alias != local else '')
                     for local, alias in by_spec[m.group(2)]]
            return 'var { %s } = __kodama_require(%r);' % (', '.join(parts), dep)

        out = _IMPORT_RE.sub(imp_repl, source)
        # 'export function f' -> 'function f'  (keep the declaration)
        out = _EXPORT_DECL_RE.sub(lambda m: '%s%s %s' % (
            m.group(1), m.group(2), m.group(3)), out)
        out = _EXPORT_LIST_RE.sub('', out)
        if mod['exports']:
            if not out.endswith('\n'):
                out += '\n'
            out += '\n'.join('__kodama_exports.%s = %s;' % (exp, loc)
                             for exp, loc in mod['exports']) + '\n'
        return out

    parts = [
        '// auto-generated by kodama_docs/js_bundle.py — do not edit by hand.\n'
        '// Sources: the ES modules in web/ (edit those, rebuild the static\n'
        '// site). This classic-script bundle exists because browsers refuse\n'
        '// external ES modules over file:// — see STATIC_SITE.md.\n'
        '(function () {\n'
        "  'use strict';\n"
        '  var __kodama_modules = {};\n'
        '  var __kodama_cache = {};\n'
        '  function __kodama_define(id, factory) { __kodama_modules[id] = factory; }\n'
        '  function __kodama_require(id) {\n'
        '    var hit = __kodama_cache[id];\n'
        '    if (hit) return hit.exports; // cache holds the module object\n'
        '    var mod = { exports: {} };\n'
        '    __kodama_cache[id] = mod; // registered before evaluation\n'
        '    if (!__kodama_modules[id])\n'
        "      throw new Error('kodama bundle: no such module: ' + id);\n"
        '    __kodama_modules[id](mod, mod.exports, __kodama_require);\n'
        '    return mod.exports;\n'
        '  }\n\n',
    ]
    for mid in order:
        parts.append('  __kodama_define(%r, function (module, __kodama_exports, '
                     '__kodama_require) {\n' % mid)
        parts.append(transform(mid))
        parts.append('  });\n\n')
    parts.append('  __kodama_require(%r);\n' % entry)
    parts.append('})();\n')
    return ''.join(parts)


if __name__ == '__main__':  # eyeball:  python -m kodama_docs.js_bundle web sidebar.js
    import sys
    print(bundle(sys.argv[1] if len(sys.argv) > 1 else 'web',
                 sys.argv[2] if len(sys.argv) > 2 else 'sidebar.js'))
