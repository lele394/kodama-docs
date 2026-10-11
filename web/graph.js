// doc_maker /graph — codebase dependency graph (Obsidian-style).
//
// Vanilla JS + <canvas>, no dependencies. Data: /api/graph (meta/graph.json).
// Two levels:
//   files   — one node per file (plus modules); IMPORTS kept, CALLS re-
//             aggregated onto file→file pairs
//   symbols — one node per function/variable (plus files); CONTAINS,
//             CALLS and READS edges; ext/builtin symbols optional
// Interactions: wheel zoom, background pan, node drag (reheats layout),
// hover tooltip, click → doc opens in the left panel, right-hand menu
// to tune the force-layout parameters (repulsion, spring, …) live.
(function () {
  'use strict';

  var canvas = document.getElementById('graph-canvas');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var stage = document.getElementById('graph-stage');
  var tip = document.getElementById('graph-tip');
  var legend = document.getElementById('graph-legend');
  var counts = document.getElementById('graph-counts');
  var panelBody = document.getElementById('panel-body');
  var panelTitle = document.getElementById('panel-title');
  var panelBack = document.getElementById('panel-back');
  var panelOpen = document.getElementById('panel-open');
  var extChk = document.getElementById('ext-chk');
  var extInput = document.getElementById('show-ext');
  var orphanInput = document.getElementById('show-orphans');

  var COLORS = {
    file: '#3b6fd4', function: '#2e9e63', variable: '#d98a14',
    module: '#8b5cf6', builtin: '#12a594', ext: '#d6455c',
  };
  var NAMES = {
    file: 'file', function: 'function', variable: 'variable',
    module: 'module', builtin: 'builtin', ext: 'external',
  };

  // ---------------- state
  var raw = null;
  var level = 'files';
  var showExt = false;
  var showOrphans = true;

  // force-layout parameters — tunable at runtime from the right-hand menu
  var SIM_DEFAULTS = {
    repulsion: 2400,   // node-node push (kRep)
    spring: 0.08,      // edge attraction (kSpr)
    spacing: 1,        // multiplier on the level's base link distance
    center: 0.003,     // pull towards the origin
    damping: 0.8,      // velocity decay per tick
    cooling: 0.99,     // alpha decay per frame (lower = settles faster)
    speed: 30,         // max velocity per tick
  };
  var sim = {};
  Object.keys(SIM_DEFAULTS).forEach(function (k) { sim[k] = SIM_DEFAULTS[k]; });
  var nodes = [], edges = [], byId = {};
  var view = { s: 1, ox: 0, oy: 0 };
  var alpha = 0, running = false;
  var hover = null, selected = null, dragNode = null;
  var dpr = 1;
  var fg = '#1f2328';
  var accent = '#3b6fd4';

  // ---------------- small helpers
  function sanitize(name) {
    return String(name).replace(/[^A-Za-z0-9._@-]/g, '_');
  }

  // node ids: file:{rp} | fn:{rp}::{name}@{line} | var:{rp}::{name}@{line}
  function relpathOf(id) {
    if (id.indexOf('file:') === 0) return id.slice(5);
    var c = id.indexOf(':');
    var d = id.indexOf('::');
    return id.slice(c + 1, d);
  }

  function fileOf(id) { return 'file:' + relpathOf(id); }

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---------------- data / levels
  function labelOf(n) {
    if (n.kind === 'file') {
      var p = n.relpath;
      var i = p.lastIndexOf('/');
      return i >= 0 ? p.slice(i + 1) : p;
    }
    return n.name || n.id;
  }

  function buildLevel() {
    var keep = level === 'files'
      ? { file: 1, module: 1 }
      : (showExt
         ? { file: 1, function: 1, variable: 1, ext: 1, builtin: 1 }
         : { file: 1, function: 1, variable: 1 });
    nodes = []; byId = {};
    raw.nodes.forEach(function (n) {
      if (!keep[n.kind]) return;
      var v = {
        id: n.id, kind: n.kind, label: labelOf(n),
        relpath: n.relpath, name: n.name, line: n.line,
        deg: 0, x: 0, y: 0, vx: 0, vy: 0, r: 3, adj: [],
      };
      nodes.push(v); byId[n.id] = v;
    });
    var agg = {};
    raw.edges.forEach(function (e) {
      var s = e.source, t = e.target;
      if (level === 'files') { s = fileOf(s); t = fileOf(t); }
      if (!byId[s] || !byId[t] || s === t) return;
      var k = s + '\u0000' + t + '\u0000' + e.type;
      if (!agg[k]) agg[k] = { s: s, t: t, type: e.type, count: 0 };
      agg[k].count++;
    });
    edges = Object.keys(agg).map(function (k) { return agg[k]; });
    edges.forEach(function (e) {
      byId[e.s].deg++; byId[e.t].deg++;
      byId[e.s].adj.push(byId[e.t]);
      byId[e.t].adj.push(byId[e.s]);
    });
    if (!showOrphans) {
      // drop nodes with no edges; edges only ever touch kept nodes
      nodes = nodes.filter(function (v) { return v.deg > 0; });
      byId = {};
      nodes.forEach(function (v) { byId[v.id] = v; });
    }
    var base = level === 'files' ? 4 : 2.6;
    var mult = level === 'files' ? 1.7 : 1.15;
    nodes.forEach(function (v) {
      v.r = base + Math.sqrt(v.deg) * mult;
    });
    initPositions();
    hover = null;
    tip.hidden = true;
  }

  // deterministic initial positions: files on a circle, symbols near their
  // file, everything else scattered a bit further out.
  function initPositions() {
    var rnd = mulberry32(level === 'files' ? 1 : 2);
    var files = nodes.filter(function (v) { return v.kind === 'file'; });
    var nf = files.length || 1;
    var R = 80 + 26 * Math.sqrt(nf);
    files.forEach(function (f, i) {
      var a = (i / nf) * Math.PI * 2;
      f.x = R * Math.cos(a); f.y = R * Math.sin(a);
      f.vx = 0; f.vy = 0;
    });
    nodes.forEach(function (v) {
      if (v.kind === 'file') return;
      var host = byId['file:' + v.relpath];
      if (host) {
        var a = rnd() * Math.PI * 2;
        var d = 20 + rnd() * 50;
        v.x = host.x + d * Math.cos(a);
        v.y = host.y + d * Math.sin(a);
      } else {
        var a2 = rnd() * Math.PI * 2;
        var d2 = R * (1.1 + rnd() * 0.4);
        v.x = d2 * Math.cos(a2);
        v.y = d2 * Math.sin(a2);
      }
      v.vx = 0; v.vy = 0;
    });
  }

  // ---------------- force layout (grid-binned repulsion + springs)
  var CELL = 100;

  function tick() {
    var n = nodes.length;
    if (!n) return;
    var grid = {};
    var i, v;
    for (i = 0; i < n; i++) {
      v = nodes[i];
      var k = Math.floor(v.x / CELL) + ',' + Math.floor(v.y / CELL);
      (grid[k] || (grid[k] = [])).push(v);
    }
    var rest = (level === 'files' ? 110 : 70) * sim.spacing;
    var kRep = sim.repulsion, kSpr = sim.spring,
        damp = sim.damping, center = sim.center;
    for (i = 0; i < n; i++) {
      v = nodes[i];
      var fx = 0, fy = 0;
      var cx = Math.floor(v.x / CELL), cy = Math.floor(v.y / CELL);
      for (var gx = cx - 1; gx <= cx + 1; gx++) {
        for (var gy = cy - 1; gy <= cy + 1; gy++) {
          var bucket = grid[gx + ',' + gy];
          if (!bucket) continue;
          for (var bi = 0; bi < bucket.length; bi++) {
            var o = bucket[bi];
            if (o === v) continue;
            var dx = v.x - o.x, dy = v.y - o.y;
            var d2 = dx * dx + dy * dy;
            if (d2 < 1e-4) { dx = 0.5; dy = 0.5; d2 = 0.5; }
            if (d2 > 9 * CELL * CELL) continue;
            var d = Math.sqrt(d2);
            var f = (kRep / d2) * alpha;
            fx += (dx / d) * f; fy += (dy / d) * f;
          }
        }
      }
      for (var ai = 0; ai < v.adj.length; ai++) {
        var o2 = v.adj[ai];
        var dx2 = o2.x - v.x, dy2 = o2.y - v.y;
        var d3 = Math.sqrt(dx2 * dx2 + dy2 * dy2) || 1;
        var f2 = (d3 - rest) * kSpr * alpha;
        fx += (dx2 / d3) * f2; fy += (dy2 / d3) * f2;
      }
      fx -= v.x * center * alpha;
      fy -= v.y * center * alpha;
      v.vx = (v.vx + fx) * damp;
      v.vy = (v.vy + fy) * damp;
    }
    for (i = 0; i < n; i++) {
      v = nodes[i];
      if (v === dragNode) continue;
      var sp = Math.sqrt(v.vx * v.vx + v.vy * v.vy);
      if (sp > sim.speed) { v.vx *= sim.speed / sp; v.vy *= sim.speed / sp; }
      v.x += v.vx; v.y += v.vy;
    }
  }

  function startSim() {
    if (running) return;
    running = true;
    var step = function () {
      tick(); tick();
      draw();
      alpha *= sim.cooling;
      if (alpha > 0.02) {
        requestAnimationFrame(step);
      } else {
        running = false;
        fitView();
        draw();
      }
    };
    requestAnimationFrame(step);
  }

  function reheat(a) {
    if (alpha < a) alpha = a;
    if (!running) startSim();
  }

  // ---------------- view / drawing
  function resize() {
    dpr = window.devicePixelRatio || 1;
    var w = stage.clientWidth, h = stage.clientHeight;
    var pw = Math.round(w * dpr), ph = Math.round(h * dpr);
    if (canvas.width !== pw || canvas.height !== ph) {
      canvas.width = pw;
      canvas.height = ph;
    }
  }

  function worldOf(clientX, clientY) {
    var r = canvas.getBoundingClientRect();
    return {
      x: (clientX - r.left - view.ox) / view.s,
      y: (clientY - r.top - view.oy) / view.s,
    };
  }

  function fitView() {
    if (!nodes.length) return;
    var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    nodes.forEach(function (v) {
      if (v.x < minx) minx = v.x;
      if (v.x > maxx) maxx = v.x;
      if (v.y < miny) miny = v.y;
      if (v.y > maxy) maxy = v.y;
    });
    var w = stage.clientWidth, h = stage.clientHeight;
    var bw = (maxx - minx) || 1, bh = (maxy - miny) || 1;
    var s = Math.min(w / (bw + 140), h / (bh + 140));
    s = Math.max(0.04, Math.min(4, s));
    view.s = s;
    view.ox = (w - (minx + maxx) * s) / 2;
    view.oy = (h - (miny + maxy) * s) / 2;
  }

  var EDGE_STYLE = {
    CALLS: { color: 'rgba(110,120,140,0.55)', dash: [], width: 1.2 },
    IMPORTS: { color: 'rgba(59,111,212,0.55)', dash: [6, 4], width: 1.2 },
    CONTAINS: { color: 'rgba(110,120,140,0.30)', dash: [], width: 1 },
    READS: { color: 'rgba(217,138,20,0.65)', dash: [3, 3], width: 1.1 },
  };

  function draw() {
    if (!raw) return;
    resize();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(
      dpr * view.s, 0, 0, dpr * view.s, dpr * view.ox, dpr * view.oy
    );

    // edges, batched per style for speed
    var groups = {};
    edges.forEach(function (e) {
      (groups[e.type] || (groups[e.type] = [])).push(e);
    });
    Object.keys(groups).forEach(function (t) {
      var st = EDGE_STYLE[t] || EDGE_STYLE.CALLS;
      ctx.beginPath();
      groups[t].forEach(function (e) {
        var a = byId[e.s], b = byId[e.t];
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
      });
      ctx.strokeStyle = st.color;
      ctx.lineWidth = st.width;
      ctx.setLineDash(st.dash);
      ctx.stroke();
    });
    ctx.setLineDash([]);

    // nodes
    for (var i = 0; i < nodes.length; i++) {
      var v = nodes[i];
      ctx.beginPath();
      ctx.arc(v.x, v.y, v.r, 0, Math.PI * 2);
      ctx.fillStyle = COLORS[v.kind] || '#999';
      ctx.fill();
    }

    // hover / selection rings
    [hover, selected].forEach(function (v) {
      if (!v) return;
      ctx.beginPath();
      ctx.arc(v.x, v.y, v.r + 3, 0, Math.PI * 2);
      ctx.strokeStyle = v === selected ? accent : 'rgba(30,35,45,0.6)';
      ctx.lineWidth = 2 / view.s;
      ctx.stroke();
    });

    // labels: zoomed in, hubs, or the hovered/selected node
    var fs = 11 / view.s;
    ctx.font = '500 ' + fs + 'px "Segoe UI", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = fg;
    var showAll = view.s > 1.6;
    var hubDeg = level === 'files' ? 20 : 25;
    for (var j = 0; j < nodes.length; j++) {
      var w = nodes[j];
      if (w === hover || w === selected || showAll || w.deg >= hubDeg) {
        ctx.fillText(w.label, w.x, w.y + w.r + fs * 1.1);
      }
    }
  }

  // ---------------- picking / tooltip
  function pick(clientX, clientY) {
    var p = worldOf(clientX, clientY);
    var best = null, bd = Infinity;
    var slack = 6 / view.s;
    for (var i = 0; i < nodes.length; i++) {
      var v = nodes[i];
      var dx = v.x - p.x, dy = v.y - p.y;
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d < v.r + slack && d < bd) { bd = d; best = v; }
    }
    return best;
  }

  // ---------------- events
  canvas.addEventListener('wheel', function (e) {
    e.preventDefault();
    var f = Math.exp(-e.deltaY * 0.0015);
    var s2 = Math.max(0.03, Math.min(10, view.s * f));
    f = s2 / view.s;
    var r = canvas.getBoundingClientRect();
    var px = e.clientX - r.left, py = e.clientY - r.top;
    view.ox = px - (px - view.ox) * f;
    view.oy = py - (py - view.oy) * f;
    view.s = s2;
    draw();
  }, { passive: false });

  var drag = null;
  canvas.addEventListener('mousedown', function (e) {
    var v = pick(e.clientX, e.clientY);
    drag = {
      node: v,
      sx: e.clientX, sy: e.clientY,
      ox: view.ox, oy: view.oy,
      vx: v ? v.x : 0, vy: v ? v.y : 0,
      moved: false,
    };
    if (v) dragNode = v;
    canvas.style.cursor = 'grabbing';
    e.preventDefault();
  });

  window.addEventListener('mousemove', function (e) {
    if (drag) {
      var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      if (drag.node) {
        drag.node.x = drag.vx + dx / view.s;
        drag.node.y = drag.vy + dy / view.s;
        reheat(0.25);
      } else {
        view.ox = drag.ox + dx;
        view.oy = drag.oy + dy;
        draw();
      }
      return;
    }
    if (resizing) return;
    if (e.target !== canvas) {
      // pointer over the top bar / doc panel / menus — no hover there
      if (hover) { hover = null; tip.hidden = true; draw(); }
      return;
    }
    hover = pick(e.clientX, e.clientY);
    canvas.style.cursor = hover ? 'pointer' : 'grab';
    if (hover) {
      tip.hidden = false;
      tip.textContent = hover.label + ' — ' + NAMES[hover.kind]
        + (hover.relpath ? '  ·  ' + hover.relpath : '');
      var r = stage.getBoundingClientRect();
      tip.style.left = (e.clientX - r.left + 14) + 'px';
      tip.style.top = (e.clientY - r.top + 14) + 'px';
    } else {
      tip.hidden = true;
    }
    draw();
  });

  window.addEventListener('mouseup', function (e) {
    if (!drag) return;
    var d = drag;
    drag = null;
    dragNode = null;
    canvas.style.cursor = 'grab';
    if (!d.moved && d.node) openNode(d.node);
  });

  canvas.addEventListener('mouseleave', function () {
    if (drag) return;
    hover = null;
    tip.hidden = true;
    draw();
  });

  window.addEventListener('resize', function () { draw(); });

  // ---------------- panel resize (drag the strip between panel and graph)
  var resizer = document.getElementById('panel-resizer');
  var panelEl = document.getElementById('graph-panel');
  var PANEL_MIN = 280;
  var PANEL_MAX = Math.min(1400, Math.max(600,
    Math.floor((window.innerWidth || 1280) * 0.8)));
  try {
    var savedW = parseFloat(window.localStorage
      .getItem('doc-maker:panel-w') || '');
    if (savedW >= PANEL_MIN) panelEl.style.width = savedW + 'px';
  } catch (e) { /* storage unavailable — use the default width */ }
  var resizing = false;
  resizer.addEventListener('mousedown', function (e) {
    resizing = true;
    resizer.classList.add('active');
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
  window.addEventListener('mousemove', function (e) {
    if (!resizing) return;
    var w = Math.max(PANEL_MIN, Math.min(PANEL_MAX, Math.round(e.clientX)));
    if (panelEl.style.width !== (w + 'px')) {
      panelEl.style.width = w + 'px';
      draw();
    }
  });
  window.addEventListener('mouseup', function () {
    if (!resizing) return;
    resizing = false;
    resizer.classList.remove('active');
    document.body.style.userSelect = '';
    try {
      window.localStorage.setItem('doc-maker:panel-w', panelEl.style.width);
    } catch (e) { /* ignore */ }
  });

  // ---------------- controls
  var levelRadios = document.querySelectorAll('input[name=level]');
  Array.prototype.forEach.call(levelRadios, function (r) {
    r.addEventListener('change', function () {
      if (!r.checked) return;
      level = r.value;
      extInput.disabled = (level === 'files');
      extChk.classList.toggle('disabled', level === 'files');
      rebuild();
    });
  });

  extInput.addEventListener('change', function (e) {
    showExt = e.target.checked;
    if (level === 'symbols') rebuild();
  });

  orphanInput.addEventListener('change', function (e) {
    showOrphans = e.target.checked;
    rebuild();
  });

  document.getElementById('graph-reset').addEventListener('click', function () {
    fitView();
    draw();
  });

  // ---------------- layout parameters (right-hand menu)
  var paramsEl = document.getElementById('params');
  var paramsToggle = document.getElementById('params-toggle');
  var paramsReset = document.getElementById('params-reset');
  var paramsSliders = document.getElementById('params-sliders');

  var SLIDERS = [
    { key: 'repulsion', min: 0, max: 8000, step: 100 },
    { key: 'spring', min: 0, max: 0.4, step: 0.005 },
    { key: 'spacing', min: 0.2, max: 3, step: 0.05 },
    { key: 'center', min: 0, max: 0.03, step: 0.0005 },
    { key: 'damping', min: 0.4, max: 0.99, step: 0.01 },
    { key: 'cooling', min: 0.9, max: 0.999, step: 0.001 },
    { key: 'speed', min: 5, max: 100, step: 1 },
  ];

  function syncSliders() {
    SLIDERS.forEach(function (d) {
      paramsSliders.querySelector('#in-' + d.key).value = sim[d.key];
      paramsSliders.querySelector('#val-' + d.key).textContent = sim[d.key];
    });
  }

  SLIDERS.forEach(function (d) {
    var label = document.createElement('label');
    label.innerHTML =
      '<span class="pname"><span>' + d.key + '</span><b id="val-' + d.key
      + '"></b></span>'
      + '<input type="range" id="in-' + d.key + '" min="' + d.min + '"'
      + ' max="' + d.max + '" step="' + d.step + '">';
    paramsSliders.appendChild(label);
    label.querySelector('input').addEventListener('input', function (e) {
      sim[d.key] = parseFloat(e.target.value);
      paramsSliders.querySelector('#val-' + d.key).textContent = sim[d.key];
      reheat(0.6);
    });
  });
  syncSliders();

  paramsToggle.addEventListener('click', function () {
    paramsEl.hidden = !paramsEl.hidden;
  });
  paramsReset.addEventListener('click', function () {
    Object.keys(SIM_DEFAULTS).forEach(function (k) { sim[k] = SIM_DEFAULTS[k]; });
    syncSliders();
    reheat(0.6);
  });

  function rebuild() {
    buildLevel();
    updateLegend();
    updateCounts();
    startSim();
  }

  function updateLegend() {
    var kinds = {};
    nodes.forEach(function (v) { kinds[v.kind] = 1; });
    legend.innerHTML = Object.keys(kinds)
      .map(function (k) {
        return '<span class="lg"><i style="background:' + COLORS[k] + '"></i>'
          + NAMES[k] + 's</span>';
      })
      .join('');
  }

  function updateCounts() {
    counts.textContent = nodes.length + ' nodes · ' + edges.length + ' edges';
  }

  // ---------------- left panel
  var docStack = [];

  function urlFor(v) {
    if (v.kind === 'file') {
      return { url: '/files/' + v.relpath + '.md', frag: null };
    }
    if (v.kind === 'function') {
      return {
        url: '/files/' + v.relpath + '.md',
        frag: 'fn-' + sanitize(v.name) + '-' + v.line,
      };
    }
    if (v.kind === 'variable') {
      return { url: '/files/' + v.relpath + '.md', frag: 'variables' };
    }
    return null;
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function infoCard(v) {
    return '<h1>' + esc(v.label) + '</h1>'
      + '<p>' + NAMES[v.kind] + ' symbol — no documentation page.</p>'
      + (v.relpath ? '<p>Referenced from <code>' + esc(v.relpath) + '</code></p>' : '')
      + '<p class="panel-hint">These are external or built-in names the codebase '
      + 'calls but does not define; show/hide them with the '
      + '"external symbols" toggle.</p>';
  }

  function afterHtml(html, title) {
    panelBody.innerHTML = html;
    panelTitle.textContent = title || '';
    panelBody.scrollTop = 0;
    if (window.hljs && window.hljs.highlightAll) {
      try { window.hljs.highlightAll(); } catch (err) { /* ignore */ }
    }
  }

  function loadDoc(t, frag) {
    if (panelOpen) panelOpen.hidden = false;
    afterHtml('<p class="panel-hint">loading…</p>', t.url);
    // body-only endpoint so the panel doesn't embed the page shell
    var fetchUrl = t.url.indexOf('/files/') === 0
      ? '/page' + t.url
      : t.url;
    fetch(fetchUrl)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        // t.url is an absolute path, so any origin serves to resolve the
        // relative links it contains; a fixed one keeps this location-
        // independent.
        var ORIGIN = 'http://docmaker.local';
        var base = new URL(ORIGIN + t.url);
        var bodyEl = doc.body;
        Array.prototype.forEach.call(bodyEl.querySelectorAll('a[href]'),
          function (a) {
            var href = a.getAttribute('href');
            if (!href) return;
            if (href.charAt(0) === '#') {
              a.setAttribute('data-doc-frag', href.slice(1));
              a.removeAttribute('href');
              return;
            }
            var abs;
            try { abs = new URL(href, base).href; } catch (err) { return; }
            var hash = abs.indexOf('#');
            var path = hash >= 0 ? abs.slice(0, hash) : abs;
            var pathOnly = path.indexOf(ORIGIN) === 0
              ? path.slice(ORIGIN.length) : path;
            if (pathOnly.indexOf('/files/') === 0
                && pathOnly.slice(-3) === '.md') {
              a.setAttribute('data-doc-url', '/' + pathOnly.slice(1));
              if (hash >= 0) a.setAttribute('data-doc-frag', abs.slice(hash + 1));
              a.removeAttribute('href');
            } else {
              a.setAttribute('href', abs);
              a.setAttribute('target', '_blank');
            }
          });
        var h1 = bodyEl.querySelector('h1');
        panelBody.innerHTML = bodyEl.innerHTML;
        panelTitle.textContent = h1 ? h1.textContent : t.url;
        if (window.hljs && window.hljs.highlightAll) {
          try { window.hljs.highlightAll(); } catch (err) { /* ignore */ }
        }
        if (frag) {
          var el = panelBody.querySelector('#' + CSS.escape(frag));
          if (el) el.scrollIntoView();
        } else {
          panelBody.scrollTop = 0;
        }
      })
      .catch(function (err) {
        afterHtml(
          '<p class="panel-err">Could not load ' + esc(t.url) + ' ('
          + esc(err && err.message || err) + '). '
          + '<a href="' + esc(t.url) + '" target="_blank">open in a tab</a></p>',
          t.url
        );
      });
  }

  function openNode(v) {
    selected = v;
    draw();
    var t = urlFor(v);
    if (!t) {
      docStack = [];
      panelBack.hidden = true;
      if (panelOpen) panelOpen.hidden = true;
      afterHtml(infoCard(v), NAMES[v.kind]);
      return;
    }
    docStack = [t];
    panelBack.hidden = true;
    loadDoc(t, t.frag);
  }

  panelBody.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a') : null;
    if (!a) return;
    var frag = a.getAttribute('data-doc-frag');
    var docUrl = a.getAttribute('data-doc-url');
    if (docUrl) {
      // a link to another doc page (optionally with an anchor)
      e.preventDefault();
      var t = { url: docUrl };
      docStack.push(t);
      if (docStack.length > 25) docStack.shift();
      panelBack.hidden = false;
      loadDoc(t, frag || null);
      return;
    }
    if (frag) {
      // an in-page anchor
      e.preventDefault();
      var el = panelBody.querySelector('#' + CSS.escape(frag));
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  });

  panelBack.addEventListener('click', function () {
    if (docStack.length > 1) {
      docStack.pop();
      loadDoc(docStack[docStack.length - 1], null);
    }
  });

  if (panelOpen) panelOpen.addEventListener('click', function () {
    var top = docStack[docStack.length - 1];
    if (!top) return;
    window.open(top.url + (top.frag ? '#' + top.frag : ''), '_blank',
                'noopener');
  });

  // ---------------- theme-aware colors
  function refreshTheme() {
    var cs = getComputedStyle(document.body);
    fg = cs.getPropertyValue('--fg').trim() || fg;
    accent = cs.getPropertyValue('--accent').trim() || accent;
    if (raw) draw();
  }
  var themeLink = document.getElementById('doc-theme');
  if (themeLink && 'MutationObserver' in window) {
    new MutationObserver(refreshTheme).observe(themeLink, {
      attributes: true, attributeFilter: ['href'],
    });
  }

  // ---------------- init
  fetch('/api/graph')
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      raw = data;
      rebuild();
    })
    .catch(function (err) {
      stage.style.display = 'flex';
      stage.style.alignItems = 'center';
      stage.style.justifyContent = 'center';
      stage.innerHTML = '<p class="panel-err">No graph data found at '
        + '/api/graph — ' + esc(err && err.message || err)
        + '. Re-run the doc pipeline to build meta/graph.json.</p>';
      legend.innerHTML = '';
      counts.textContent = '';
    });
})();
