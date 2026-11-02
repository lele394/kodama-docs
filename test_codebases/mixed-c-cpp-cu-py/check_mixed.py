"""Structural checks for the mixed C / C++ / CUDA / Python fixture.

Run after:

    .venv/bin/python main.py \
        --config test_codebases/mixed-c-cpp-cu-py/settings.yaml --no-llm
    .venv/bin/python test_codebases/mixed-c-cpp-cu-py/check_mixed.py

No third-party imports: this reads the generated JSON/markdown directly.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
DOCS = os.path.join(ROOT, 'docs')
SRC = os.path.join(ROOT, 'codebase')

FAILS = []


def check(cond, msg):
    if cond:
        print(f'  ok   {msg}')
    else:
        print(f'  FAIL {msg}')
        FAILS.append(msg)


def load_json(name):
    with open(os.path.join(DATA, name), 'r', encoding='utf-8') as fh:
        return json.load(fh)


def load_text(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def main():
    symbols = load_json('symbols.json')
    graph = load_json('graph.json')
    diag = load_json('diagnostics.json')

    files = symbols['files']
    by_rel = {f['relpath']: f for f in files}
    nodes = {n['id']: n for n in graph['nodes']}
    edges = graph['edges']

    print('invariants')
    check(len(nodes) == len(graph['nodes']), 'graph node ids are unique')
    check(all(e.get('source') in nodes and e.get('target') in nodes
              for e in edges), 'every edge endpoint exists')
    bad_status = []
    for e in edges:
        et = e.get('type')
        if et == 'CALLS':
            ok = e.get('status') in ('resolved', 'inferred', 'builtin')
        elif et == 'IMPORTS':
            ok = e.get('status') == 'resolved'
        elif et == 'READS':
            ok = True
        else:
            continue
        if bool(e.get('resolution_success')) != ok:
            bad_status.append(e)
    check(not bad_status,
          'resolution_success agrees with edge status')

    source_lines = {}
    line_problems = []
    for f in files:
        rel = f['relpath']
        lines = load_text(os.path.join(SRC, rel)).splitlines()
        source_lines[rel] = lines
        for fn in f.get('functions') or []:
            lo, hi = fn['line'], fn['end_line']
            if not (1 <= lo <= hi <= len(lines)):
                line_problems.append(f'{rel}:{fn["name"]} lines {lo}-{hi}')
                continue
            body = '\n'.join(lines[lo - 1:hi])
            if body != fn['body']:
                line_problems.append(f'{rel}:{fn["name"]} body mismatch')
        for c in f.get('classes') or []:
            if not (1 <= c['line'] <= c['end_line'] <= len(lines)):
                line_problems.append(f'{rel}:class {c["name"]}')
        for v in f.get('file_vars') or []:
            if not (1 <= v['line'] <= len(lines)):
                line_problems.append(f'{rel}:var {v["name"]}')
    check(not line_problems,
          'line numbers and exact-body slices match the source'
          + (f' ({line_problems[:3]})' if line_problems else ''))

    contains_problems = []
    for f in files:
        fid = 'file:' + f['relpath']
        targets = {e['target'] for e in edges
                   if e.get('type') == 'CONTAINS' and e['source'] == fid}
        wanted = [f'fn:{f["relpath"]}::{fn["name"]}@{fn["line"]}'
                  for fn in f.get('functions') or []]
        wanted += [f'cls:{f["relpath"]}::{c["name"]}@{c["line"]}'
                   for c in f.get('classes') or []]
        wanted += [f'var:{f["relpath"]}::{v["name"]}@{v["line"]}'
                   for v in f.get('file_vars') or []]
        contains_problems += [w for w in wanted if w not in targets]
    check(not contains_problems,
          'every symbol has a CONTAINS edge from its file')

    print('files')
    expected = {
        'c/core.c', 'c/core.h',
        'include/mixed/version.h',
        'cuda/kernels.cu', 'cuda/kernels.cuh',
        'cpp/engine.cpp', 'cpp/engine.hpp', 'cpp/math.hpp',
        'cpp/bindings.cpp',
        'python/mixed_py/__init__.py',
        'python/mixed_py/bridge.py',
        'python/mixed_py/host.py',
    }
    check(set(by_rel) == expected,
          f'all {len(expected)} fixture files analyzed')
    check(all(f.get('status') == 'ok' for f in files),
          'every file analyzed without errors')
    check(diag['analysis']['counts']['failed'] == 0,
          'diagnostics report zero analysis failures')
    check(all(n.get('lang') in {'c-family', 'python'}
              for n in nodes.values()
              if n.get('kind') in {'file', 'function', 'class', 'variable'}),
          'source graph nodes carry a language family')

    def fn(rel, name, qualified=None):
        hits = [n for n in nodes.values()
                if n.get('kind') == 'function'
                and n.get('relpath') == rel and n.get('name') == name]
        if qualified is not None:
            hits = [n for n in hits if n.get('qualified') == qualified]
        return hits[0] if hits else None

    def cls(rel, name):
        hits = [n for n in nodes.values()
                if n.get('kind') == 'class'
                and n.get('relpath') == rel and n.get('name') == name]
        return hits[0] if hits else None

    def calls(node):
        if node is None:
            return []
        out = []
        for e in edges:
            if e.get('type') == 'CALLS' and e.get('source') == node['id']:
                tgt = nodes.get(e.get('target'), {})
                out.append((tgt.get('relpath'), tgt.get('name'),
                            e.get('status')))
        return out

    def imports(rel):
        src = 'file:' + rel
        out = []
        for e in edges:
            if e.get('type') == 'IMPORTS' and e.get('source') == src:
                tgt = nodes.get(e.get('target'), {})
                out.append((tgt.get('relpath'), e.get('status')))
        return out

    def reads(node):
        if node is None:
            return []
        out = []
        for e in edges:
            if e.get('type') == 'READS' and e.get('source') == node['id']:
                tgt = nodes.get(e.get('target'), {})
                out.append((tgt.get('relpath'), tgt.get('name')))
        return out

    def bridges(node):
        if node is None:
            return []
        return [(nodes.get(e.get('target'), {}).get('relpath'),
                 nodes.get(e.get('target'), {}).get('name'))
                for e in edges
                if e.get('type') == 'BRIDGES'
                and e.get('source') == node['id']]

    def exports(rel):
        src = 'file:' + rel
        return [(nodes.get(e.get('target'), {}).get('relpath'),
                 nodes.get(e.get('target'), {}).get('name'))
                for e in edges
                if e.get('type') == 'EXPORTS' and e.get('source') == src]

    print('symbols')
    for rel, name in [
        ('c/core.c', 'c_add'),
        ('c/core.c', 'c_scale'),
        ('c/core.c', 'mixed_version'),
        ('c/core.c', 'mixed_call_count'),
        ('cuda/kernels.cu', 'saxpy_kernel'),
        ('cuda/kernels.cu', 'warp_sum'),
        ('cuda/kernels.cu', 'launch_saxpy'),
        ('cpp/engine.cpp', 'step'),
        ('cpp/engine.cpp', 'run_gpu'),
        ('cpp/engine.cpp', 'describe'),
        ('cpp/math.hpp', 'clamp_value'),
        ('cpp/bindings.cpp', 'py_add'),
        ('cpp/bindings.cpp', 'PYBIND11_MODULE'),
        ('python/mixed_py/bridge.py', 'run_gpu'),
        ('python/mixed_py/host.py', 'run_demo'),
    ]:
        check(fn(rel, name) is not None, f'{rel}: function {name}')

    check(fn('cpp/engine.cpp', 'step',
             qualified='mixed.Engine.step') is not None,
          'C++ method qualified name is mixed.Engine.step')
    check(cls('cpp/engine.hpp', 'Engine') is not None,
          'C++ class Engine extracted')
    check(cls('python/mixed_py/bridge.py', 'CNative') is not None,
          'Python class CNative extracted')
    check(cls('python/mixed_py/bridge.py', 'Engine') is not None,
          'Python class Engine extracted')
    c_add = fn('c/core.c', 'c_add')
    check(c_add is not None and c_add['params'] == ['a', 'b'],
          'C function params extracted')
    saxpy = fn('cuda/kernels.cu', 'saxpy_kernel')
    check(saxpy is not None and saxpy['params'] == ['a', 'x', 'y', 'n'],
          'CUDA kernel params extracted')

    print('developer comments')
    c_add_sym = next(fn for fn in by_rel['c/core.c']['functions']
                     if fn['name'] == 'c_add')
    check(c_add_sym.get('developer_comment') ==
          'Add two integers and count the operation.\n'
          'This is a multiline block comment: both lines must stick to the '
          'function.', 'multiline block comment glues to a C function')
    c_native_sym = next(c for c in
                        by_rel['python/mixed_py/bridge.py']['classes']
                        if c['name'] == 'CNative')
    check((c_native_sym.get('developer_comment') or '').startswith(
              'Multiline developer comment on a Python class'),
          'multiline line-comment run glues to a Python class')
    core_max = by_rel['c/core.c']['file_vars'][0]
    check(core_max['name'] == 'CORE_MAX' and
          (core_max.get('developer_comment') or '').startswith(
              'Maximum count reported'),
          'multiline comment glues to a C macro')

    legacy = fn('cpp/engine.cpp', 'legacy_entry')
    legacy_math = cls('cpp/math.hpp', 'LegacyMath')
    legacy_add = fn('cpp/math.hpp', 'legacy_add')
    check(legacy is not None and legacy.get('skip_llm') is True,
          'kodama-docs-llm:skip marks a function')
    check(legacy_math is not None and
          legacy_math.get('skip_llm') is True,
          'kodama-docs-llm:skip marks a class')
    add_node = nodes.get(legacy_add['id']) if legacy_add else None
    check(add_node is not None and add_node.get('skip_llm') is True,
          'class skip propagates to its methods')
    legacy_add_sym = next(fn for fn in by_rel['cpp/math.hpp']['functions']
                          if fn['name'] == 'legacy_add')
    check(legacy_add_sym.get('skip_llm') is True,
          'class skip is persisted in symbols.json')
    check('LLM generation:** skipped' in
          load_text(os.path.join(DOCS, 'files', 'cpp', 'engine.cpp.md')),
          'skipped function renders the LLM-skip note')
    check('_LLM skipped_' in
          load_text(os.path.join(DOCS, 'files', 'cpp', 'math.hpp.md')),
          'skipped class/member renders the LLM-skip note')
    fn_records = []
    rec_dir = os.path.join(DATA, 'functions')
    if os.path.isdir(rec_dir):
        for name in os.listdir(rec_dir):
            if name.endswith('.json'):
                with open(os.path.join(rec_dir, name), 'r',
                          encoding='utf-8') as fh:
                    fn_records.append(json.load(fh))
    rec_names = {r.get('name') for r in fn_records}
    check('legacy_entry' not in rec_names and 'legacy_add' not in rec_names,
          'no LLM record was generated for skipped symbols')

    check(by_rel['c/core.c']['dialect'] == 'c'
          and by_rel['c/core.h']['dialect'] == 'c',
          'C source/header dialect is c')
    check(by_rel['cpp/engine.hpp']['dialect'] == 'cpp',
          'C++ header dialect is cpp')
    check(by_rel['cuda/kernels.cu']['dialect'] == 'cuda',
          'CUDA dialect is cuda')
    check([v['name'] for v in by_rel['c/core.c']['file_vars']]
          == ['CORE_MAX', 'call_count'],
          'C globals/macros extracted (include guards skipped)')
    check(not by_rel['c/core.h']['file_vars'],
          'header include guard is not a file variable')
    check([v['name'] for v in by_rel['include/mixed/version.h']['file_vars']]
          == ['MIXED_VERSION'],
          'public version macro extracted')

    print('reads')
    check(('c/core.c', 'call_count') in reads(fn('c/core.c', 'c_add')),
          'c_add reads the global call_count')
    check(('c/core.c', 'call_count') in
          reads(fn('c/core.c', 'mixed_call_count'))
          and ('c/core.c', 'CORE_MAX') in
          reads(fn('c/core.c', 'mixed_call_count')),
          'mixed_call_count reads call_count and CORE_MAX')
    check(('include/mixed/version.h', 'MIXED_VERSION') in
          reads(fn('c/core.c', 'mixed_version')),
          'mixed_version reads MIXED_VERSION through its quoted include')
    check(not reads(fn('cpp/engine.cpp', 'step')),
          'C++ class fields are not misreported as file-variable reads')

    print('includes')
    for rel, target in [
        ('c/core.c', 'c/core.h'),
        ('c/core.c', 'include/mixed/version.h'),
        ('cpp/engine.hpp', 'c/core.h'),
        ('cpp/engine.hpp', 'cuda/kernels.cuh'),
        ('cpp/engine.hpp', 'cpp/math.hpp'),
        ('cpp/engine.cpp', 'cpp/engine.hpp'),
        ('cpp/engine.cpp', 'c/core.h'),
        ('cpp/bindings.cpp', 'cpp/engine.hpp'),
        ('cuda/kernels.cu', 'cuda/kernels.cuh'),
    ]:
        edges_out = imports(rel)
        check((target, 'resolved') in edges_out,
              f'{rel} includes {target} (resolved)')

    print('calls')
    scale = fn('c/core.c', 'c_scale')
    check(('c/core.c', 'c_add', 'resolved') in calls(scale),
          'C same-file call c_scale -> c_add (resolved)')

    step = fn('cpp/engine.cpp', 'step')
    step_calls = calls(step)
    check(('c/core.c', 'c_add', 'inferred') in step_calls,
          'C++ -> C call step -> c_add (inferred)')
    check(('c/core.c', 'c_scale', 'inferred') in step_calls,
          'C++ -> C call step -> c_scale (inferred)')

    run_gpu = fn('cpp/engine.cpp', 'run_gpu')
    check(('cuda/kernels.cu', 'launch_saxpy', 'inferred') in calls(run_gpu),
          'C++ -> CUDA call run_gpu -> launch_saxpy (inferred)')

    launch = fn('cuda/kernels.cu', 'launch_saxpy')
    check(('cuda/kernels.cu', 'saxpy_kernel', 'resolved') in calls(launch),
          'CUDA kernel launch launch_saxpy -> saxpy_kernel (resolved)')

    py_add = fn('cpp/bindings.cpp', 'py_add')
    check(('c/core.c', 'c_add', 'inferred') in calls(py_add),
          'C++ binding py_add -> C c_add (inferred)')

    describe = fn('cpp/engine.cpp', 'describe')
    check(('cpp/math.hpp', 'clamp_value', 'resolved') in calls(describe),
          'C++ namespace-local template call describe -> clamp_value '
          '(resolved)')

    print('pybind11 bridge')
    py_engine = cls('python/mixed_py/bridge.py', 'Engine')
    check(cls('cpp/engine.hpp', 'Engine') is not None
          and ('cpp/engine.hpp', 'Engine') in bridges(py_engine),
          'Python Engine class BRIDGES to C++ mixed.Engine')
    check(('cpp/engine.hpp', 'Engine') in exports('cpp/bindings.cpp'),
          'bindings.cpp EXPORTS the C++ Engine class')
    check(('cpp/engine.cpp', 'step') in exports('cpp/bindings.cpp'),
          'bindings.cpp EXPORTS Engine::step')
    check(('cpp/bindings.cpp', 'py_add') in exports('cpp/bindings.cpp'),
          'bindings.cpp EXPORTS the module-level py_add function')
    check(('cpp/bindings.cpp', 'resolved') in
          imports('python/mixed_py/bridge.py'),
          'import mixed_native resolves to cpp/bindings.cpp')
    engine_init = fn('python/mixed_py/bridge.py', '__init__',
                     qualified='Engine.__init__')
    check(('cpp/engine.hpp', 'Engine', 'resolved') in calls(engine_init),
          'Python Engine() construction resolves to the C++ class')
    unresolved = {d.get('module') for d in
                  diag['graph']['unresolved_imports']}
    check('mixed_native' not in unresolved,
          'the pybind11 module is no longer an unresolved import')

    print('cross-language boundaries')
    cn_add = fn('python/mixed_py/bridge.py', 'add', qualified='CNative.add')
    cn_scale = fn('python/mixed_py/bridge.py', 'scale',
                  qualified='CNative.scale')
    check(('c/core.c', 'c_add', 'inferred') in calls(cn_add),
          'ctypes CNative.add -> C c_add stays inferred')
    check(('c/core.c', 'c_scale', 'inferred') in calls(cn_scale),
          'ctypes CNative.scale -> C c_scale stays inferred')
    check(('c/core.c', 'c_add', 'resolved') not in calls(cn_add),
          'ctypes calls are not passed off as resolved bindings')

    print('rendering')
    cu_page = os.path.join(DOCS, 'files', 'cuda', 'kernels.cu.md')
    check(os.path.isfile(cu_page), 'CUDA page exists')
    if os.path.isfile(cu_page):
        text = load_text(cu_page)
        check('```cpp' in text, '.cu page uses the cpp syntax fence')
    c_page = os.path.join(DOCS, 'files', 'c', 'core.c.md')
    check(os.path.isfile(c_page) and '```c' in load_text(c_page),
          '.c page exists and uses the c syntax fence')
    index = load_text(os.path.join(DOCS, 'index.md'))
    check('cuda/kernels.cu.md' in index,
          'index lists the CUDA file')

    print()
    if FAILS:
        print(f'{len(FAILS)} check(s) failed')
        return 1
    print('all mixed-codebase checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
