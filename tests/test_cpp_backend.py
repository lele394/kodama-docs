"""C/C++/CUDA backend + mixed-language graph tests (no LLM).

Run:  .venv/bin/python tests/test_cpp_backend.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backends
from kodama_docs import graph as gmod


def mk(src, rel):
    r = backends.extract(src, rel)
    r['relpath'] = rel
    r['lines'] = len(src.splitlines())
    r['size'] = len(src.encode())
    r['status'] = 'ok'
    return r


def fn_names(r):
    return [f['name'] for f in r['functions']]


def calls_out(g, node_id):
    return sorted((v, d.get('status')) for _u, v, d in g.edges(node_id, data=True)
                  if d.get('type') == 'CALLS')


def reads_out(g, node_id):
    return sorted(v for _u, v, d in g.edges(node_id, data=True)
                  if d.get('type') == 'READS')


def test_c_extraction():
    src = """#include "core.h"
#define MAX 100
#define ADD(a, b) ((a) + (b))
static int counter = 0;
/* Add two integers. */
int c_add(int a, int b) { return a + b; }
int c_scale(int value, int factor) { return c_add(value, 0) * factor; }
"""
    r = mk(src, 'c/core.c')
    assert r['lang'] == 'c-family'
    assert r['dialect'] == 'c'
    assert fn_names(r) == ['ADD', 'c_add', 'c_scale']
    add = r['functions'][1]
    assert add['params'] == ['a', 'b']
    assert add['qualified'] == 'c_add'
    assert add['developer_comment'] == 'Add two integers.'
    assert add['body'] == 'int c_add(int a, int b) { return a + b; }'
    assert [v['name'] for v in r['file_vars']] == ['MAX', 'counter']
    assert r['file_vars'][0]['init'] == 'number'
    assert r['imports'] == [{'module': 'core.h', 'line': 1}]
    assert {'callee': 'c_add', 'line': 7, 'method': None} in r['calls']


def test_header_prototypes_are_not_duplicate_functions():
    hdr = """#ifndef CORE_H
#define CORE_H
int c_add(int a, int b);
#endif
"""
    r = mk(hdr, 'c/core.h')
    assert r['functions'] == []
    assert r['file_vars'] == []  # include guards are plumbing, not API


def test_cpp_class_methods_and_qualified_names():
    src = """namespace mixed {
class Engine {
public:
    Engine(int n);
    int step(int x);
};
Engine::Engine(int n) : size_(n) {}
int Engine::step(int x) { return helper_.run(c_add(x, size_)); }
}
"""
    r = mk(src, 'cpp/engine.cpp')
    cls = r['classes'][0]
    assert (cls['name'], cls['qualified'], cls['line'], cls['end_line']) == \
        ('Engine', 'mixed.Engine', 2, 6)
    assert cls.get('developer_comment') is None
    assert fn_names(r) == ['Engine', 'step']
    step = r['functions'][1]
    assert step['qualified'] == 'mixed.Engine.step'
    assert step['params'] == ['x']
    assert {'callee': 'helper_', 'line': 8, 'method': 'run'} in r['calls']
    assert {'callee': 'c_add', 'line': 8, 'method': None} in r['calls']


def test_cuda_kernel_launch_is_a_call():
    src = """#include "kernels.cuh"
__global__ void k(float* x, int n) {
    int i = threadIdx.x;
    if (i < n) x[i] = i;
}
void launch(float* x, int n) {
    k<<<1, 256>>>(x, n);
    cudaDeviceSynchronize();
}
"""
    r = mk(src, 'cuda/kernels.cu')
    assert r['lang'] == 'c-family'
    assert r['dialect'] == 'cuda'
    assert fn_names(r) == ['k', 'launch']
    assert r['functions'][0]['params'] == ['x', 'n']
    assert {'callee': 'k', 'line': 7, 'method': None} in r['calls']
    assert {'callee': 'cudaDeviceSynchronize', 'line': 8,
            'method': None} in r['calls']


def test_include_candidates():
    assert 'c/core.h' in backends.module_candidates('core.h', 'c/impl.c')
    assert 'c/core.h' in backends.module_candidates(
        '../c/core.h', 'cpp/engine.cpp')
    assert 'include/mixed/version.h' in backends.module_candidates(
        '../include/mixed/version.h', 'c/core.c')


def test_mixed_graph_links_c_family():
    c = mk("int c_add(int a, int b) { return a + b; }\n", 'c/core.c')
    cpp = mk("""int step(int x) { return c_add(x, 0); }
""", 'cpp/engine.cpp')
    cu = mk("""__global__ void k(float* x) { x[0] = 0; }
void launch(float* x) { k<<<1, 1>>>(x); cudaDeviceSynchronize(); }
""", 'cuda/kernels.cu')
    g, diag = gmod.build_graph([c, cpp, cu])
    assert calls_out(g, 'fn:cpp/engine.cpp::step@1') == \
        [('fn:c/core.c::c_add@1', 'inferred')]
    assert set(calls_out(g, 'fn:cuda/kernels.cu::launch@2')) == {
        ('fn:cuda/kernels.cu::k@1', 'resolved'),
        ('builtin:cudaDeviceSynchronize', 'builtin')}
    assert not diag['ambiguous_calls']


def test_c_included_variable_is_a_reads_edge():
    hdr = mk("#define VERSION 1\nint version(void);\n", 'include/version.h')
    src = mk('#include "../include/version.h"\n'
             'int get_version(void) { return VERSION; }\n', 'c/use.c')
    g, _diag = gmod.build_graph([hdr, src])
    assert reads_out(g, 'fn:c/use.c::get_version@2') == \
        ['var:include/version.h::VERSION@1']


def test_multiline_comments_and_llm_skip_directive():
    src = '''/*
This
is
multiline comment
*/
int main() { return 0; }

/*
kodama-docs-llm:skip
Skip this one.
*/
class Legacy {
public:
    int run() { return 1; }
};

/*
kodama-docs-llm:skip
*/
#define OLD 1
'''
    r = mk(src, 'cpp/demo.cpp')
    main = next(fn for fn in r['functions'] if fn['name'] == 'main')
    assert main['developer_comment'] == 'This\nis\nmultiline comment'
    legacy = next(c for c in r['classes'] if c['name'] == 'Legacy')
    assert legacy['skip_llm'] is True
    assert legacy['developer_comment'] == 'Skip this one.'
    old = next(v for v in r['file_vars'] if v['name'] == 'OLD')
    assert old['skip_llm'] is True
    assert old.get('developer_comment') is None

    g, _diag = gmod.build_graph([r])
    run = next(n for n in g.nodes.values()
               if n.get('kind') == 'function' and n.get('name') == 'run')
    assert run.get('skip_llm') is True  # class skip propagated


def test_cross_file_class_skip_propagates():
    hdr = mk('''/*
kodama-docs-llm:skip
*/
namespace n { class A { public: int f(); }; }
''', 'cpp/a.hpp')
    impl = mk('int n::A::f() { return 1; }\n', 'cpp/a.cpp')
    g, _diag = gmod.build_graph([hdr, impl])
    f = next(n for n in g.nodes.values()
             if n.get('kind') == 'function' and n.get('name') == 'f')
    assert f.get('skip_llm') is True


def test_python_multiline_comments_and_skip():
    src = '''# kodama-docs-llm:skip
# first line
# second line
class Legacy:
    def run(self):
        return 1

def keep():
    return 2
'''
    r = mk(src, 'py/demo.py')
    legacy = r['classes'][0]
    assert legacy['developer_comment'] == 'first line\nsecond line'
    assert legacy.get('skip_llm') is True
    g, _diag = gmod.build_graph([r])
    run = next(n for n in g.nodes.values()
               if n.get('kind') == 'function' and n.get('name') == 'run')
    keep = next(n for n in g.nodes.values()
                if n.get('kind') == 'function' and n.get('name') == 'keep')
    assert run.get('skip_llm') is True
    assert not keep.get('skip_llm')


def test_lua_multiline_comment_and_skip():
    src = '''--[[
first
second
]]
function keep()
    return 1
end

-- kodama-docs-llm:skip
local legacy = 1
'''
    r = mk(src, 'lua/demo.lua')
    keep = next(fn for fn in r['functions'] if fn['name'] == 'keep')
    legacy = next(v for v in r['file_vars'] if v['name'] == 'legacy')
    assert keep['developer_comment'] == 'first\nsecond'
    assert legacy['skip_llm'] is True
    assert legacy.get('developer_comment') is None


def test_pybind_bindings_create_exports_and_bridges():
    hdr = mk("namespace ns { class Engine { public: int step(int); }; }\n",
             'cpp/engine.hpp')
    impl = mk("int ns::Engine::step(int x) { return x; }\n",
              'cpp/engine.cpp')
    bind = mk("""int py_add(int a, int b) { return a + b; }
PYBIND11_MODULE(mixed_native, m) {
    m.def("add", &py_add);
    py::class_<ns::Engine>(m, "Engine").def("step", &ns::Engine::step);
}
""", 'cpp/bindings.cpp')
    py = mk("""import mixed_native as native
class Engine:
    def __init__(self):
        self.native = native.Engine()
""", 'py/facade.py')

    recs = {(b['kind'], b['name']): b['target'] for b in bind['bindings']}
    assert recs[('function', 'add')] == 'py_add'
    assert recs[('class', 'Engine')] == 'ns.Engine'
    assert recs[('method', 'step')] == 'ns.Engine.step'

    g, _diag = gmod.build_graph([hdr, impl, bind, py])
    py_cls = 'cls:py/facade.py::Engine@2'
    cpp_cls = 'cls:cpp/engine.hpp::Engine@1'
    assert g.has_edge(py_cls, cpp_cls)
    assert any(d.get('type') == 'BRIDGES'
               for d in g.get_edge_data(py_cls, cpp_cls).values())
    assert g.has_edge('file:py/facade.py', 'file:cpp/bindings.cpp')
    assert g.has_edge('file:cpp/bindings.cpp', cpp_cls)
    assert calls_out(g, 'fn:py/facade.py::__init__@3') == \
        [(cpp_cls, 'resolved')]


def test_c_header_dialect_and_include_guard():
    c_h = mk("#ifndef CORE_H\n#define CORE_H\nint f(void);\n#endif\n",
             'c/core.h')
    cpp_h = mk("#pragma once\nnamespace n { class A {}; }\n",
               'cpp/api.h')
    assert c_h['dialect'] == 'c' and c_h['file_vars'] == []
    assert cpp_h['dialect'] == 'cpp'


def test_cpp_namespace_call_resolves_but_python_bare_method_does_not():
    cpp = mk("""namespace mixed {
int helper() { return 1; }
int run() { return helper(); }
}
""", 'cpp/use.cpp')
    g, _diag = gmod.build_graph([cpp])
    assert calls_out(g, 'fn:cpp/use.cpp::run@3') == \
        [('fn:cpp/use.cpp::helper@2', 'resolved')]


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'ok   {t.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL {t.__name__}: {e}')
    print()
    if failed:
        print(f'{failed} cpp backend test(s) failed')
        return 1
    print(f'{len(tests)} cpp backend tests passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
