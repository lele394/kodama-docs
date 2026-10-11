"""doc_maker — live terminal UI (TUI) for the concurrent LLM phase.

Built on Rich (https://github.com/Textualize/rich): one table row per
agent (file, symbol, stage, time on task), a progress bar, run stats,
and a rolling tail of the log. Rich measures the terminal itself and
re-lays everything out on every refresh, so the panel follows live
window resizes and is never clipped or misaligned, at any width.

While the TUI is active, log() lines are routed into the panel instead
of being printed, so the panel geometry is never disturbed by
interleaved output.

If stdout is not a TTY (piped or job-captured run) the panel is skipped
and logging prints as usual.
"""
import atexit
import sys
import threading
import time

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text


def _fmt_dur(s):
    s = max(0, int(s))
    if s < 60:
        return f'{s}s'
    if s < 3600:
        return f'{s // 60}m{s % 60:02d}s'
    return f'{s // 3600}h{(s % 3600) // 60:02d}m'


def _stage_style(stage):
    return {'describe': 'green', 'merge': 'cyan'}.get(stage or '', 'yellow')


class _Frame:
    """Renderable that re-renders the current TUI state each refresh."""

    def __init__(self, tui):
        self.tui = tui

    def __rich_console__(self, console, options):
        yield self.tui._render()


class TUI:
    """Thread-safe shared agent state + Rich-based terminal panel."""

    def __init__(self, enabled=True, worker_count=1, total=0,
                 interval=0.5, force=False, kinds=None):
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
            'kinds': [{'label': k, 'total': int(v), 'done': 0}
                      for k, v in (kinds or {}).items()],
            'workers': [{'id': i + 1, 'name': f'agent-{i + 1}',
                         'state': 'idle', 'file': None, 'symbol': None,
                         'stage': None, 'since': None, 'first_at': None,
                         'finished': 0, 'failed': 0}
                        for i in range(self.worker_count)],
        }
        self._logs = []
        self._logs_lock = threading.Lock()
        self._console = None
        self._live = None

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        if not self.enabled:
            return False
        self.active = self.force or (hasattr(sys.stdout, 'isatty')
                                     and sys.stdout.isatty())
        if not self.active:
            return False
        self._console = Console()
        self._live = Live(_Frame(self), console=self._console,
                          refresh_per_second=max(2, 1.0 / self.interval))
        self._live.start(refresh=True)
        atexit.register(self._exit)
        return True

    def _exit(self):
        self.stop()

    def stop(self):
        if not self.active:
            return
        self.active = False
        try:
            if self._live:
                self._live.stop()
            if self._console:
                self._console.print()
        except Exception:  # noqa: BLE001
            pass

    # -- rendering (runs on Rich's refresh thread) --------------------------
    def _render(self):
        now = time.time()
        s = self.snapshot()
        width = self._console.width if self._console else 80
        head = Text(f'doc_maker · llm phase · {s["total"]} tasks · '
                    f'{self.worker_count} agents', style='bold')
        head.truncate(width, overflow='ellipsis')
        parts = [head]

        table = Table(box=box.SIMPLE, pad_edge=False, padding=(0, 1),
                      header_style='bold', expand=False)
        table.add_column('agent', width=8, no_wrap=True, overflow='ellipsis')
        table.add_column('symbol', min_width=12, no_wrap=True,
                         overflow='ellipsis')
        table.add_column('stage', min_width=9, no_wrap=True, justify='right')
        table.add_column('time', min_width=6, no_wrap=True, justify='right')
        table.add_column('done', min_width=4, no_wrap=True, justify='right')
        for wk in s['workers']:
            if wk['state'] == 'working':
                sym = f'{wk["file"]} :: {wk["symbol"]}'
                stage = wk['stage'] or '…'
                t = _fmt_dur(now - (wk['since'] or now))
            else:
                sym = Text('(idle)', style='dim')
                stage = 'waiting'
                t = ''
            done = str(wk['finished'])
            if wk['failed']:
                done += f' ({wk["failed"]}✗)'
            table.add_row(wk['name'], sym,
                          Text(f'[{stage}]', style=_stage_style(stage)),
                          t, done)
        parts.append(table)

        kinds = s.get('kinds') or []
        labels = [k['label'] for k in kinds] + ['total']
        pad = max(len(l) for l in labels) + 2

        def bar(done, total, label):
            frac = min(1.0, done / total) if total else 0.0
            tail = f'  {done}/{total}'
            if label == 'total':
                tail += f'  {frac * 100:.0f}%'
            bw = max(8, width - len(label) - pad + 2 - len(tail) - 1)
            fill = int(round(bw * frac))
            t = Text(label.ljust(pad), style='bold')
            t.append('█' * fill, style='bold green')
            t.append('░' * (bw - fill), style='dim')
            t.append(tail, style='bold')
            t.truncate(width, overflow='ellipsis')
            return t

        for k in kinds:
            parts.append(bar(k['done'], k['total'], k['label']))
        parts.append(bar(s['done'], s['total'], 'total'))

        avg = s['time_sum'] / s['done'] if s['done'] else 0.0
        stats = Text.assemble(
            ('generated ', 'green'), (str(s['generated']), 'bold green'),
            ('   ·   cached ', 'dim'), (str(s['skipped']), 'bold'),
            ('   ·   failed ', 'red' if s['failed'] else 'dim'),
            (str(s['failed']), 'bold red' if s['failed'] else 'bold'),
            ('   ·   avg ', 'dim'), (_fmt_dur(avg) + '/task', 'bold'),
            ('   ·   elapsed ', 'dim'),
            (_fmt_dur(now - s['started_at']), 'bold'))
        remain = max(0, s['total'] - s['done'])
        if remain and avg:
            stats.append('   ·   eta ~'
                         + _fmt_dur(remain * avg / self.worker_count),
                         style='bold')
        stats.truncate(width, overflow='ellipsis')
        parts.append(stats)

        height = self._console.height if self._console else None
        loglines = 4
        if height:
            loglines = max(2, min(6, height - (self.worker_count + 8)))
        with self._logs_lock:
            tail = list(self._logs[-loglines:])
        for line in tail:
            tline = Text(line, style='dim')
            tline.truncate(width, overflow='ellipsis')
            parts.append(tline)
        return Group(*parts)

    # -- reporting (called from worker threads) -----------------------------
    def sink(self, line):
        with self._logs_lock:
            self._logs.append(line)
            if len(self._logs) > 60:
                del self._logs[:len(self._logs) - 60]
        if self._live:
            self._live.refresh()

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

    def job_end(self, wid, duration, generated=False, failed=False,
                kind=None):
        with self.lock:
            s, w = self.st, self._w(wid)
            s['done'] += 1
            s['time_sum'] += duration
            if kind is not None:
                for k in s['kinds']:
                    if k['label'] == kind:
                        k['done'] += 1
                        break
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
            s['kinds'] = [dict(k) for k in s['kinds']]
        done = s['done']
        s['avg_seconds'] = s['time_sum'] / done if done else 0.0
        remain = max(0, s['total'] - done)
        s['eta_seconds'] = (remain * s['avg_seconds'] / self.worker_count
                            if remain else 0.0)
        return s
