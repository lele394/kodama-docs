"""Small shared helpers: logging, id sanitizing, truncation."""
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


def sanitize_id(idstr: str) -> str:
    """Filesystem-safe form of a symbol id (for intermediate file names)."""
    return re.sub(r'[^A-Za-z0-9._@-]', '_', idstr)


def trunc(s, n: int) -> str:
    s = str(s or '')
    return s if len(s) <= n else s[:n] + ' …'
