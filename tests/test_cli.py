"""CLI safety tests: bare invocation must not start a pipeline.

Run:  .venv/bin/python tests/test_cli.py
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'main.py')


def run(args, cwd):
    return subprocess.run([sys.executable, MAIN, *args], cwd=cwd,
                          capture_output=True, text=True, timeout=120)


def test_bare_command_prints_help():
    with tempfile.TemporaryDirectory() as td:
        r = run([], td)
        assert r.returncode == 0, r
        assert 'usage:' in r.stdout
        assert '--config' in r.stdout
        assert not os.path.exists(os.path.join(td, 'doc'))
        assert not os.path.exists(os.path.join(td, 'data'))


def test_pipeline_requires_explicit_config():
    with tempfile.TemporaryDirectory() as td:
        r = run(['--no-llm'], td)
        assert r.returncode == 2, r
        assert '--config PATH is required' in r.stderr
        assert not os.path.exists(os.path.join(td, 'doc'))
        assert not os.path.exists(os.path.join(td, 'data'))


def test_backend_listing_needs_no_config():
    with tempfile.TemporaryDirectory() as td:
        r = run(['--list-backends'], td)
        assert r.returncode == 0, r
        assert 'kodama-cpp' in r.stdout
        assert 'kodama-python' in r.stdout


def test_init_creates_settings_and_prompts():
    with tempfile.TemporaryDirectory() as td:
        r = run(['init'], td)
        assert r.returncode == 0, r
        settings = os.path.join(td, 'settings.yaml')
        assert os.path.isfile(settings)
        with open(settings, 'r', encoding='utf-8') as fh:
            text = fh.read()
        assert 'source_dir: "."' in text
        for name in ('function.txt', 'function_chunk.txt',
                     'variable.txt', 'summary.txt'):
            assert os.path.isfile(os.path.join(td, 'prompts', name))
        # refuse to clobber an existing config without --force
        r = run(['init'], td)
        assert r.returncode != 0, r
        assert 'already exists' in (r.stdout + r.stderr)
        r = run(['init', '--force'], td)
        assert r.returncode == 0, r


def test_init_config_runs_without_llm():
    with tempfile.TemporaryDirectory() as td:
        r = run(['init'], td)
        assert r.returncode == 0, r
        r = run(['--config', 'settings.yaml', '--no-llm'], td)
        assert r.returncode == 0, r
        assert os.path.isfile(os.path.join(td, 'doc', 'index.md'))


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
        print(f'{failed} CLI test(s) failed')
        return 1
    print(f'{len(tests)} CLI tests passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
