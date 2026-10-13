"""Resolver regression tests (no LLM, in-memory).

Run:  .venv/bin/python tests/test_resolver.py

Covers the P0 review findings:
  * symbols resolve via imports, lexical scope and aliases — never by
    scan-order guesswork;
  * resolution outcomes are classified (resolved / inferred / builtin /
    external) and ambiguity produces a diagnostic, not a guessed edge;
  * the require-alias contract (local A = require('m') -> A:method()).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backends  # noqa: E402
from kodama_docs import graph as gmod  # noqa: E402


def mk(src, rel):
    r = backends.extract(src, rel)
    r['relpath'] = rel
    r['lines'] = len(src.splitlines())
    r['size'] = len(src.encode())
    r['status'] = 'ok'
    return r


py = lambda src, base: mk(src, base + '.py')
lua = lambda src, base: mk(src, base + '.lua')


def calls_out(g, node_id):
    return sorted((v, d.get('status')) for u, v, d in g.edges(node_id, data=True)
                  if d.get('type') == 'CALLS')


def test_from_import_binding_resolves_to_imported_module():
    """The P0-1 case: `from users import validate` must link to users.py,
    not to a same-named function in payments.py (old scan-order bug)."""
    users = py("""
def validate(amount):
    return amount > 0
""", 'users')
    payments = py("""
def validate(amount):
    return amount < 1000
""", 'payments')
    checkout = py("""
from users import validate

def charge(amount):
    return validate(amount)
""", 'checkout')
    g, diag = gmod.build_graph([users, payments, checkout])
    assert calls_out(g, 'fn:checkout.py::charge@4') == \
        [('fn:users.py::validate@2', 'resolved')]
    assert not diag['ambiguous_calls']


def test_builtin_wins_over_project_function_same_name():
    """`math.sqrt` is stdlib even though the project defines `sqrt`."""
    mathutil = py("""
def sqrt(x):
    return x ** 0.5
""", 'mathutil')
    use = py("""
import math

def go(x):
    return math.sqrt(x)
""", 'use')
    g, diag = gmod.build_graph([mathutil, use])
    assert calls_out(g, 'fn:use.py::go@4') == \
        [('builtin:math.sqrt', 'builtin')]
    assert not diag['ambiguous_calls']


def test_aliased_imports_disambiguate():
    """Two modules, one shared symbol, two distinct local names: both
    calls resolve (status: resolved), no diagnostic."""
    a1 = py("def validate(x):\n    return 1\n", 'alpha')
    a2 = py("def validate(x):\n    return 2\n", 'beta')
    amb = py("""
from alpha import validate as va
from beta import validate as vb

def go(x):
    va(x)
    vb(x)
""", 'amb')
    g, diag = gmod.build_graph([a1, a2, amb])
    edges = calls_out(g, 'fn:amb.py::go@5')
    assert ('fn:alpha.py::validate@1', 'resolved') in edges
    assert ('fn:beta.py::validate@1', 'resolved') in edges
    assert not diag['ambiguous_calls']


def test_double_bound_name_is_ambiguous_not_guessed():
    """One local name bound to two different symbols: no edge is written
    and the call site is recorded with its candidates (P0-2)."""
    a1 = py("def validate(x):\n    return 1\n", 'alpha')
    a2 = py("def validate(x):\n    return 2\n", 'beta')
    amb2 = py("""
from alpha import validate
from beta import validate as validate

def go(x):
    validate(x)
""", 'amb2')
    g, diag = gmod.build_graph([a1, a2, amb2])
    assert calls_out(g, 'fn:amb2.py::go@5') == []
    assert len(diag['ambiguous_calls']) == 1
    d = diag['ambiguous_calls'][0]
    assert d['name'] == 'validate'
    assert d['candidates'] == ['alpha.py::validate@1', 'beta.py::validate@1']


def test_lua_require_alias_resolves_method():
    """`local NBody = require('physics.nbody')` then `NBody:new(...)` must
    resolve to nbody's `new` (require-alias contract)."""
    nbody = lua("""
NBody = {}
function NBody:new(mass)
  self.mass = mass
  return self
end
""", 'nbody')
    sim = lua("""
local NBody = require('physics.nbody')

function make()
  local b = NBody:new(1.0)
  return b
end
""", 'sim')
    g, diag = gmod.build_graph([nbody, sim])
    assert ('fn:sim.lua::make@4', 'fn:nbody.lua::new@3', 'resolved') in \
        [(u, v, d.get('status')) for u, v, d in g.edges(data=True)
         if d.get('type') == 'CALLS']


def test_unbound_object_unique_method_is_inference():
    """`sim:step(...)` on a local instance (no import binding): the only
    project match is an inference — kept, but marked `inferred`."""
    body = lua("""
local Body = {}
function Body:step(dt)
end
""", 'body')
    world = lua("""
local sim = make_sim()

function run()
  sim:step(0.016)
end
""", 'world')
    g, diag = gmod.build_graph([body, world])
    assert ('fn:body.lua::step@3', 'inferred') in calls_out(
        g, 'fn:world.lua::run@4')


def test_import_as_module_binding():
    """`import payments as p` then `p.fee(x)` resolves to payments.py."""
    pmod = py("""
def fee(x):
    return x * 0.1
""", 'payments')
    caller = py("""
import payments as p

def go(x):
    return p.fee(x)
""", 'caller')
    g, diag = gmod.build_graph([pmod, caller])
    assert calls_out(g, 'fn:caller.py::go@4') == \
        [('fn:payments.py::fee@2', 'resolved')]


def test_local_scope_wins_over_same_name_elsewhere():
    local = py("""
def helper(x):
    return 1

def go(x):
    return helper(x)
""", 'local')
    other = py("""
def helper(x):
    return 2
""", 'other')
    g, diag = gmod.build_graph([local, other])
    assert calls_out(g, 'fn:local.py::go@5') == \
        [('fn:local.py::helper@2', 'resolved')]
    assert not diag['ambiguous_calls']


def test_unbound_multiple_project_names_are_ambiguous():
    """Bare name defined twice project-wide, no import binding: no edge,
    diagnostic with both candidates (never pick one silently)."""
    multi1 = py("""
def compute(x):
    return 1
""", 'm1')
    multi2 = py("""
def compute(x):
    return 2
""", 'm2')
    muse = py("""
def go(x):
    return compute(x)
""", 'muse')
    g, diag = gmod.build_graph([multi1, multi2, muse])
    assert calls_out(g, 'fn:muse.py::go@2') == []
    assert diag['ambiguous_calls'][0]['name'] == 'compute'
    assert diag['ambiguous_calls'][0]['candidates'] == \
        ['m1.py::compute@2', 'm2.py::compute@2']


def test_lua_builtin_math_sqrt():
    lb = lua("""
function f(x)
  return math.sqrt(x)
end
""", 'lb')
    g, diag = gmod.build_graph([lb])
    assert ('builtin:math.sqrt', 'builtin') in calls_out(g, 'fn:lb.lua::f@2')


def main():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith('test_') and callable(v)]
    for fn in fns:
        fn()
        print(f'ok   {fn.__name__}')
    print(f'\n{len(fns)} resolver tests passed')


if __name__ == '__main__':
    main()
