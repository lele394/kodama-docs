"""Small shared helpers: logging, id sanitizing, truncation."""
import re
import time


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sanitize_id(idstr: str) -> str:
    """Filesystem-safe form of a symbol id (for intermediate file names)."""
    return re.sub(r'[^A-Za-z0-9._@-]', '_', idstr)


def trunc(s, n: int) -> str:
    s = str(s or '')
    return s if len(s) <= n else s[:n] + ' …'
