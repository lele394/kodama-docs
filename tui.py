"""doc_maker — live terminal UI (TUI) for the concurrent LLM phase.

Stdlib only: ANSI escape codes painted into a fixed panel in the terminal.
One line per agent (file, symbol, stage, time on task), a progress bar,
run stats, and a rolling tail of the log. While the TUI is active, log()
lines are routed into the panel instead of being printed, so the panel
geometry is never disturbed by interleaved output.

If stdout is not a TTY (piped or job-captured run) the panel is skipped
and logging prints as usual.
"""
import atexit
import os
import re
import shutil
import sys
import threading
import time

_ANSI = re.compile(r'\x1b\[[0-9;]*m')


def _fmt_dur(s):
    s = max(0, int(s))
    if s < 60:
        return f'{s}s'
    if s < 3600:
        return f'{s // 60}m{s % 60:02d}s'
    return f'{s // 3600}h{(s % 3600) // 60:02d}m'


class TUI:
    """Thread-safe shared agent state + optional terminal panel."""

    def __init__(self, enabled=True, worker_count=1, total=0,
                 interval=0.5, force=False):
        self.enabled = bool(enabled)
        self.worker_count = max(1, int(worker_count))
        self.interval = max(0.2, float(interval))
        self.force = bool(force)
        self.active = False
        self.lock = threading.Lock()
        self.st = {
            'started_at': time.time(),
            'total': int(total),
            'done': 0, 'failed': 0, 'skipped': 0, 'generated': 0,
            'time_sum': 0.0,
            'workers': [{'id': i + 1, 'name': f'agent-{i + 1}',
                         'state': 'idle', 'file': None, 'symbol': None,
                         'stage': None, 'since': None, 'first_at': None,
                         'finished': 0, 'failed': 0}
                        for i in range(self.worker_count)],
        }
        self._logs = []
        self._logs_lock = threading.Lock()
        self._thread = None
        self._height = 0
        self._drawn = 0
        self._cols = 100
        self._loglines = 4
        self._restored = False

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        if not self.enabled:
            return False
        self.active = self.force or (hasattr(sys.stdout, 'isatty')
                                     and sys.stdout.isatty())
        if not self.active:
            return False
        if os.name == 'nt':
            os.system('')  # enables ANSI VT processing on Windows 10+
        rows, cols = shutil.get_terminal_size((24, 100))
        self._cols = max(60, min(cols, 120))
        self._loglines = max(2, min(6, rows - (self.worker_count + 5)))
        self._height = self.worker_count + 4 + self._loglines
        sys.stdout.write('\x1b[?25l')  # hide cursor while painting
        self._draw()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        atexit.register(self._restore)
        return True

    def stop(self):
        if not self.active:
            return
        try:
            self._draw()
            sys.stdout.write('\n')
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass
        self.active = False
        self._restore()

    def _restore(self):
        if self._restored:
            return
        self._restored = True
        try:
            sys.stdout.write('\x1b[?25h')
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass

    def _loop(self):
        while self.active:
            time.sleep(self.interval)
            try:
                self._draw()
            except Exception:  # noqa: BLE001
                break

    # -- painting ----------------------------------------------------------
    def _draw(self):
        out = sys.stdout
        with self.lock:
            frame = self._frame()
        if self._drawn:
            out.write(f'\x1b[{self._height}A')  # back to panel top
        for line in frame:
            out.write('\x1b[2K' + line + '\n')
        out.flush()
        self._drawn = self._height

    @staticmethod
    def _clip(s, w):
        """Truncate to w *visible* columns, keeping ANSI codes intact."""
        if len(_ANSI.sub('', s)) <= w:
            return s
        out, vis, i, n = [], 0, 0, len(s)
        while i < n and vis < w:
            m = _ANSI.match(s, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
            out.append(s[i])
            vis += 1
            i += 1
        return ''.join(out) + '\x1b[0m'

    def _frame(self):
        now = time.time()
        s = self.st
        w = self._cols - 1
        L = []
        head = (f'doc_maker · llm phase · {s["total"]} tasks · '
                f'{self.worker_count} agents')
        L.append(self._clip(f'\x1b[1m{head}\x1b[0m', w))
        for wk in s['workers']:
            if wk['state'] == 'working':
                mid = f'{wk["file"]} :: {wk["symbol"]}'
                stage = wk['stage'] or '…'
                color = ('32' if stage == 'describe'
                         else '36' if stage == 'merge' else '33')
                right = (f'{_fmt_dur(now - (wk["since"] or now))} on task · '
                         f'{wk["finished"]} done')
            else:
                mid = '\x1b[2m(idle)\x1b[0m'
                stage = 'waiting'
                color = '2'
                right = (f'{wk["finished"]} done'
                         + (f' · {wk["failed"]} failed' if wk['failed'] else ''))
            L.append(self._clip(
                f'  {wk["name"]:<8} {mid}  \x1b[{color}m[{stage}]\x1b[0m  {right}',
                w))
        L.append(self._clip('  ' + '\x1b[2m' + '─' * 48 + '\x1b[0m', w))
        total = s['total'] or 1
        frac = min(1.0, s['done'] / total)
        barw = 32
        fill = int(round(barw * frac))
        bar = '\x1b[1;32m' + '█' * fill + '\x1b[0m\x1b[2m' + '░' * (barw - fill) + '\x1b[0m'
        L.append(self._clip(f'  {bar}  {s["done"]}/{s["total"]}   '
                            f'{frac * 100:.0f}%', w))
        avg = s['time_sum'] / s['done'] if s['done'] else 0.0
        bits = [f'\x1b[32mgenerated {s["generated"]}\x1b[0m',
                f'cached {s["skipped"]}',
                f'\x1b[31mfailed {s["failed"]}\x1b[0m' if s['failed']
                else f'failed {s["failed"]}',
                f'avg {_fmt_dur(avg)}/task',
                f'elapsed {_fmt_dur(now - s["started_at"])}']
        remain = max(0, s['total'] - s['done'])
        if remain and avg:
            bits.append(f'eta ~{_fmt_dur(remain * avg / self.worker_count)}')
        L.append(self._clip('  ' + '   ·   '.join(bits), w))
        with self._logs_lock:
            tail = self._logs[-self._loglines:]
        for m in tail:
            L.append(self._clip('  ' + m, w))
        return L

    # -- reporting (called from worker threads) -----------------------------
    def sink(self, line):
        with self._logs_lock:
            self._logs.append(line)
            if len(self._logs) > 60:
                del self._logs[:len(self._logs) - 60]

    def _w(self, wid):
        for w in self.st['workers']:
            if w['id'] == wid:
                return w
        return self.st['workers'][0]

    def job_start(self, wid, file, symbol):
        with self.lock:
            w = self._w(wid)
            w.update(state='working', file=file, symbol=symbol,
                     stage='queued', since=time.time())
            if w['first_at'] is None:
                w['first_at'] = w['since']

    def stage(self, wid, file, symbol, stage):
        with self.lock:
            w = self._w(wid)
            w.update(file=file, symbol=symbol, stage=stage)

    def job_end(self, wid, duration, generated=False, failed=False):
        with self.lock:
            s, w = self.st, self._w(wid)
            s['done'] += 1
            s['time_sum'] += duration
            w['state'] = 'idle'
            w['file'] = w['symbol'] = w['stage'] = w['since'] = None
            w['finished'] += 1
            if generated:
                s['generated'] += 1
            elif not failed:
                s['skipped'] += 1
            if failed:
                s['failed'] += 1
                w['failed'] += 1

    # -- readout -------------------------------------------------------------
    def snapshot(self):
        with self.lock:
            s = dict(self.st)
            s['workers'] = [dict(x) for x in s['workers']]
        done = s['done']
        s['avg_seconds'] = s['time_sum'] / done if done else 0.0
        remain = max(0, s['total'] - done)
        s['eta_seconds'] = (remain * s['avg_seconds'] / self.worker_count
                            if remain else 0.0)
        return s
