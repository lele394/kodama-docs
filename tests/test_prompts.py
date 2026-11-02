"""Prompt-template rendering tests (no LLM).

Run:  .venv/bin/python tests/test_prompts.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kodama_docs.prompt_templates import language_name, prompt_fields, render_prompt


def test_language_labels():
    assert language_name({'lang': 'python', 'relpath': 'a.py'}) == 'Python'
    assert language_name({'lang': 'lua', 'relpath': 'a.lua'}) == 'Lua'
    assert language_name({'lang': 'c-family', 'dialect': 'c',
                          'relpath': 'a.c'}) == 'C'
    assert language_name({'lang': 'c-family', 'dialect': 'cpp',
                          'relpath': 'a.cpp'}) == 'C++'
    assert language_name({'lang': 'c-family', 'dialect': 'cuda',
                          'relpath': 'a.cu'}) == 'CUDA'
    assert language_name({'relpath': 'a.hpp'}) == 'C++'


def test_function_fields():
    f = {'relpath': 'cpp/engine.cpp', 'lang': 'c-family',
         'dialect': 'cpp'}
    fn = {'name': 'step', 'qualified': 'mixed.Engine.step', 'line': 14,
          'end_line': 17, 'params': ['value'],
          'developer_comment': 'Advance one step.'}
    fields = prompt_fields(f, fn, 'function')
    assert fields['language'] == 'C++'
    assert fields['language_family'] == 'c-family'
    assert fields['file'] == 'cpp/engine.cpp'
    assert fields['symbol'] == 'mixed.Engine.step'
    assert fields['name'] == 'step'
    assert fields['kind'] == 'function'
    assert fields['line'] == '14' and fields['line_end'] == '17'
    assert fields['params'] == 'value'
    assert fields['fence'] == 'cpp'
    assert fields['developer_comment'] == 'Advance one step.'


def test_summary_fields_use_file_path():
    f = {'relpath': 'python/mixed_py/host.py', 'lang': 'python'}
    fields = prompt_fields(f, {'name': 'file', 'line': 1}, 'file summary')
    assert fields['language'] == 'Python'
    assert fields['symbol'] == 'python/mixed_py/host.py'
    assert fields['name'] == 'host.py'
    assert fields['kind'] == 'file summary'


def test_render_prompt_is_single_pass_and_keeps_unknown_keys():
    fields = {'language': 'C++', 'file': 'a.cpp', 'symbol': '{language}'}
    out = render_prompt(
        'This is a {language} file: {file} / {symbol} / {unknown}', fields)
    # values are not recursively re-rendered
    assert out == 'This is a C++ file: a.cpp / {language} / {unknown}'


def test_render_prompt_leaves_json_braces_alone():
    fields = {'language': 'Python'}
    out = render_prompt('{"name": "{language}", "x": 1}', fields)
    assert out == '{"name": "Python", "x": 1}'


def test_shipped_prompts_use_the_shared_language_key():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fields = prompt_fields(
        {'relpath': 'cpp/engine.cpp', 'lang': 'c-family',
         'dialect': 'cpp'},
        {'name': 'step', 'qualified': 'mixed.Engine.step', 'line': 14,
         'end_line': 17, 'params': ['value']},
        'function')
    for name in ('function.txt', 'function_chunk.txt', 'variable.txt',
                 'summary.txt'):
        with open(os.path.join(root, 'prompts', name), 'r',
                  encoding='utf-8') as fh:
            text = render_prompt(fh.read(), fields)
        assert '{language}' not in text
        assert '{file}' not in text
        assert 'C++' in text
        assert 'cpp/engine.cpp' in text


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
        print(f'{failed} prompt test(s) failed')
        return 1
    print(f'{len(tests)} prompt tests passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
