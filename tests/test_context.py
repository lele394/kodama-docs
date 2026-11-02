"""LLM context builders: the deterministic graph facts must reach the model.

Run:  .venv/bin/python tests/test_context.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kodama_docs.context import (fn_context_text, summary_context_text,  # noqa: E402
                                 var_context_text)


def test_fn_context_includes_reads_and_imports():
    fn = {'name': 'f', 'qualified': 'A.f', 'line': 3, 'end_line': 4,
          'relpath': 'a.py', 'params': ['x'], 'vararg': False,
          'body': 'def f(x):\n    return X + x'}
    out = fn_context_text(fn, ['caller'], ['g'], {'max_symbols_per_list': 5},
                          reads=['X'], imports=['mod'])
    assert 'Called by: caller' in out, out
    assert 'Calls: g' in out, out
    assert 'Reads file variables: X' in out, out
    assert 'Imports: mod' in out, out
    print('ok   test_fn_context_includes_reads_and_imports')


def test_var_context_includes_initializer():
    var = {'name': 'CONFIG', 'line': 1, 'relpath': 'a.py',
           'init': 'call', 'value': 'load_config("a")'}
    out = var_context_text(var, {})
    assert 'Initialization: call' in out, out
    assert 'load_config("a")' in out, out
    print('ok   test_var_context_includes_initializer')


def test_summary_context_includes_imports_and_classes():
    finfo = {
        'relpath': 'a.py', 'lines': 10,
        'functions': [], 'file_vars': [], 'classes': [
            {'name': 'Body', 'qualified': 'Body'}],
        'imports': [{'module': 'physics.body', 'line': 1}],
    }
    out = summary_context_text(finfo, {})
    assert 'Imports: physics.body' in out, out
    assert 'Classes: Body' in out, out
    print('ok   test_summary_context_includes_imports_and_classes')


def main():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith('test_') and callable(v)]
    for fn in fns:
        fn()
    print(f'\n{len(fns)} context tests passed')


if __name__ == '__main__':
    main()
