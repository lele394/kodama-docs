"""Local progress dashboard for the LLM phase.

Stdlib only: a ThreadingHTTPServer on localhost serving one embedded HTML
page plus a /status JSON endpoint that the page polls once per second.
The pipeline reports per-agent file/symbol/stage and overall counters.
"""
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="off">
<title>doc_maker — agent dashboard</title>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --edge:#30363d; --fg:#e6edf3;
          --dim:#8b949e; --ok:#3fb950; --warn:#d29922; --busy:#58a6ff; }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px 32px; background:var(--bg); color:var(--fg);
         font:14px/1.5 "Cascadia Code","Segoe UI",monospace; }
  h1 { font-size:18px; margin:0 0 4px; }
  .sub { color:var(--dim); margin-bottom:20px; font-size:12px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
          gap:12px; margin-bottom:24px; }
  .card { background:var(--panel); border:1px solid var(--edge); border-radius:8px;
          padding:12px 14px; min-height:118px; }
  .card.working { border-color:var(--busy); }
  .top { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .dot { width:9px; height:9px; border-radius:50%; background:var(--dim); }
  .working .dot { background:var(--busy); animation:pulse 1.2s infinite; }
  @keyframes pulse { 50% { opacity:.35; } }
  .who { font-weight:600; }
  .st { margin-left:auto; color:var(--dim); font-size:11px;
        border:1px solid var(--edge); border-radius:10px; padding:1px 8px; }
  .working .st { color:var(--busy); border-color:var(--busy); }
  .row { color:var(--dim); font-size:12px; white-space:nowrap;
         overflow:hidden; text-overflow:ellipsis; }
  .row b { color:var(--fg); font-weight:400; }
  .stage { display:inline-block; margin-top:8px; font-size:11px; color:var(--busy);
           background:rgba(88,166,255,.12); border:1px solid rgba(88,166,255,.4);
           border-radius:10px; padding:2px 10px; }
  .idle .stage { color:var(--dim); background:transparent;
                 border-color:var(--edge); }
  .foot { background:var(--panel); border:1px solid var(--edge);
          border-radius:8px; padding:14px 16px; }
  .bar { height:14px; background:#21262d; border-radius:7px; overflow:hidden;
         margin:8px 0 12px; }
  .bar i { display:block; height:100%; background:linear-gradient(90deg,var(--busy),var(--ok));
           width:0%; transition:width .5s; }
  .stats { display:flex; flex-wrap:wrap; gap:8px 28px; font-size:13px; }
  .stats b { color:var(--fg); }
  .k { color:var(--dim); }
</style></head>
<body>
<h1>doc_maker — LLM phase</h1>
<div class="sub" id="sub">connecting…</div>
<div class="grid" id="grid"></div>
<div class="foot">
  <div class="k" id="plabel">progress</div>
  <div class="bar"><i id="bar"></i></div>
  <div class="stats" id="stats"></div>
</div>
<script>
const $ = id => document.getElementById(id);
function fmt(s){ s=Math.max(0,Math.floor(s));
  const m=Math.floor(s/60), h=Math.floor(m/60);
  if(h) return h+'h '+(m%60)+'m '+(s%60)+'s';
  if(m) return m+'m '+(s%60)+'s';
  return s+'s'; }
async function tick(){
  let d;
  try { d = await (await fetch('/status')).json(); }
  catch(e){ $('sub').textContent='dashboard offline'; return; }
  const now = d.now;
  $('sub').textContent = 'started ' + new Date(d.started_at*1000).toLocaleTimeString()
    + '   ·   ' + d.total + ' tasks   ·   concurrency ' + d.workers.length;
  $('grid').innerHTML = d.workers.map(w => `
    <div class="card ${w.state==='working'?'working':'idle'}">
      <div class="top"><span class="dot"></span><span class="who">${w.name}</span>
        <span class="st">${w.state}</span></div>
      <div class="row">file&nbsp;&nbsp;<b>${w.file||'—'}</b></div>
      <div class="row">symbol <b>${w.symbol||'—'}</b></div>
      <span class="stage">${w.stage||'idle'}</span>
      <div class="row" style="margin-top:8px">
        ${w.state==='working'
          ? 'on this task '+fmt(now-(w.since||now))
          : 'since start '+fmt(now-(w.first_at||d.started_at))
            + '   ·   ' + w.finished + ' done' + (w.failed ? ' ('+w.failed+' failed)' : '')}
      </div>
    </div>`).join('');
  const done = d.done, tot = d.total || 1;
  $('plabel').textContent = `progress — ${done} / ${tot} tasks
    (${d.failed} failed, ${d.skipped} cached)`;
  $('bar').style.width = (100*done/tot) + '%';
  $('stats').innerHTML = `
    <span><span class="k">done / total</span> <b>${done} / ${d.total}</b></span>
    <span><span class="k">generated</span> <b>${d.generated}</b></span>
    <span><span class="k">time per task (avg)</span> <b>${fmt(d.avg_seconds)}</b></span>
    <span><span class="k">elapsed</span> <b>${fmt(now - d.started_at)}</b></span>
    <span><span class="k">estimated time remaining</span> <b>${d.eta_seconds>0?fmt(d.eta_seconds):'—'}</b></span>`;
}
tick(); setInterval(tick, 1000);
</script>
</body></html>"""


def _port_in_use(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.25)
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


class _Handler(BaseHTTPRequestHandler):
    dash = None  # set by Dashboard

    def log_message(self, *a):
        pass  # keep the console quiet

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == '/status':
            self._send(200, 'application/json',
                       json.dumps(self.dash.snapshot()).encode('utf-8'))
        else:
            self._send(200, 'text/html; charset=utf-8', HTML.encode('utf-8'))


class Dashboard:
    """Thread-safe shared state + optional localhost web UI."""

    def __init__(self, enabled=True, host='127.0.0.1', port=3090,
                 worker_count=1, total=0):
        self.lock = threading.Lock()
        self.url = None
        self.server = None
        self.thread = None
        self.st = {
            'started_at': time.time(),
            'total': total,
            'done': 0, 'failed': 0, 'skipped': 0, 'generated': 0,
            'time_sum': 0.0,
            'workers': [{'id': i + 1, 'name': f'agent-{i + 1}',
                         'state': 'idle', 'file': None, 'symbol': None,
                         'stage': None, 'since': None, 'first_at': None,
                         'finished': 0, 'failed': 0}
                        for i in range(max(1, worker_count))],
        }
        if not enabled:
            return
        try:
            if port and _port_in_use(host, port):
                port = 0  # fall back to an OS-assigned port
            _Handler.dash = self
            self.server = ThreadingHTTPServer((host, port), _Handler)
        except OSError:
            self.server = None  # cannot bind at all: run without the UI
            return
        self.url = f'http://{host}:{self.server.server_address[1]}'

    # -- lifecycle -------------------------------------------------------
    def start(self):
        if self.server is None:
            return False
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

    # -- reporting -------------------------------------------------------
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

    # -- readout ---------------------------------------------------------
    def snapshot(self):
        with self.lock:
            s = json.loads(json.dumps(self.st))
        s['now'] = time.time()
        done = s['done']
        s['avg_seconds'] = s['time_sum'] / done if done else 0.0
        remain = max(0, s['total'] - done)
        n = max(1, len(s['workers']))
        s['eta_seconds'] = remain * s['avg_seconds'] / n if remain else 0.0
        return s
