"""Python backend self-test protocol (``test-backend python``).

The source of truth is what CPython actually does with the fixture, not
hand-written expectations:

* ``collect_truth()`` runs the fixture and records every call site and
  import binding the runtime resolved;
* ``parse_markers()`` reads the fixture's ``# expect: ...`` lines, which pin
  the deliberately unresolvable cases the runtime cannot reach.

The generic harness (``kodama_docs/testing.py``) extracts the fixture with
the backend's ``extract``, builds the graph and checks it against these two
sources.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TEST_CODEBASE_DIR = Path(__file__).parent / 'test_codebase'

_MARKER_RE = re.compile(r'#\s*expect:\s*([A-Za-z][A-Za-z-]*)\s*(.*?)\s*$')

_KNOWN_KINDS = {
    'resolved', 'inferred', 'external', 'ambiguous', 'builtin',
    'import', 'import-unresolved',
}


def collect_truth():
    """Run the fixture's ``generate_truth.py`` and return its JSON dict.

    The fixture self-reports: it imports every executable module (with the
    fixture dir as ``sys.path[0]`` so project modules shadow stdlib) and
    records the call sites / bindings that actually resolved at runtime.
    Raises ``RuntimeError`` with the generator's stderr on failure — a broken
    fixture must fail loudly, never silently pass.
    """
    gen = TEST_CODEBASE_DIR / 'generate_truth.py'
    r = subprocess.run(
        [sys.executable, str(gen)],
        capture_output=True, text=True, check=False,
        cwd=str(TEST_CODEBASE_DIR), timeout=120)
    if r.returncode != 0:
        raise RuntimeError(
            f'truth generator failed (exit {r.returncode}):\n'
            f'{(r.stderr or r.stdout).strip()}')
    return json.loads(r.stdout)


def parse_markers(source):
    """Return the fixture's expectation markers in one source file.

    Grammar (same-line ``# expect:`` comment):
        # expect: resolved <file>::<name>
        # expect: inferred <file>::<name>
        # expect: external <label> [<label> ...]
        # expect: ambiguous
        # expect: builtin <label>
        # expect: import-unresolved
    Each marker is ``{'line', 'kind', 'targets'}`` where ``targets`` is the
    list of expected labels (empty for ``ambiguous`` / ``import-unresolved``).
    """
    out = []
    for i, line in enumerate(source.splitlines(), 1):
        m = _MARKER_RE.search(line)
        if not m:
            continue
        kind = m.group(1)
        if kind not in _KNOWN_KINDS:
            continue
        rest = m.group(2)
        targets = rest.split() if rest else []
        out.append({'line': i, 'kind': kind, 'targets': targets})
    return out
