"""Small shared helpers: logging, id sanitizing, truncation."""
import os
import re
import threading
import time

_print_lock = threading.Lock()
_sink = None  # optional log sink (set by the TUI while it is active)


def set_log_sink(fn):
    """Route log() lines to fn(line) instead of printing (None = print)."""
    global _sink
    _sink = fn


def log(msg: str) -> None:
    with _print_lock:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        if _sink is not None:
            _sink(line)
        else:
            print(line, flush=True)


#: Extensions whose highlight.js language differs from the extension itself.
#: The vendored bundle has no CUDA grammar, so .cu/.cuh render as C++ (CUDA
#: is a C++ dialect; only the <<<...>>> launch syntax goes unhighlighted).
_FENCE_ALIASES = {
    'cu': 'cpp', 'cuh': 'cpp',
    'cc': 'cpp', 'cxx': 'cpp', 'hpp': 'cpp', 'hh': 'cpp', 'hxx': 'cpp',
    # .h is ambiguous (C or C++); the C++ grammar is a superset and handles
    # both, so it is the safer highlight for header pages.
    'h': 'cpp',
}


def fence_lang(relpath: str) -> str:
    """Code-fence language label for a file path ('lua', 'py', ...)."""
    ext = os.path.splitext(str(relpath))[1].lower().lstrip('.')
    if not ext:
        return 'text'
    return _FENCE_ALIASES.get(ext, ext)


def read_env_file(path: str) -> dict:
    """Parse a small .env file (KEY=value lines, # comments) into a dict
    with lowercased keys. Values may be quoted."""
    vals = {}
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            vals[k.strip().lower()] = v.strip().strip('"').strip("'")
    return vals


def sanitize_id(idstr: str) -> str:
    """Filesystem-safe form of a symbol id (for intermediate file names)."""
    return re.sub(r'[^A-Za-z0-9._@-]', '_', idstr)


def trunc(s, n: int) -> str:
    s = str(s or '')
    return s if len(s) <= n else s[:n] + ' …'
