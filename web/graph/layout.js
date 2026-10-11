// web/graph/layout.js — build the current level (nodes/edges) and run the
// force simulation that positions them.

import { state } from './state.js';
import { tip } from './dom.js';
import { mulberry32 } from './rng.js';
import { fitView } from './view.js';
import { draw, updateLegend, updateCounts } from './draw.js';
import { labelOf, fileOf } from './util.js';

export function buildLevel() {
  var keep = state.level === 'files'
    ? { file: 1, module: 1 }
    : (state.showExt
       ? { file: 1, function: 1, variable: 1, ext: 1, builtin: 1 }
       : { file: 1, function: 1, variable: 1 });
  state.nodes = []; state.byId = {};
  state.raw.nodes.forEach(function (n) {
    if (!keep[n.kind]) return;
    var v = {
      id: n.id, kind: n.kind, label: labelOf(n),
      relpath: n.relpath, name: n.name, line: n.line,
      deg: 0, x: 0, y: 0, vx: 0, vy: 0, r: 3, adj: [],
    };
    state.nodes.push(v); state.byId[n.id] = v;
  });
  var agg = {};
  state.raw.edges.forEach(function (e) {
    var s = e.source, t = e.target;
    if (state.level === 'files') { s = fileOf(s); t = fileOf(t); }
    if (!state.byId[s] || !state.byId[t] || s === t) return;
    var k = s + '\u0000' + t + '\u0000' + e.type;
    if (!agg[k]) agg[k] = { s: s, t: t, type: e.type, count: 0 };
    agg[k].count++;
  });
  state.edges = Object.keys(agg).map(function (k) { return agg[k]; });
  state.edges.forEach(function (e) {
    state.byId[e.s].deg++; state.byId[e.t].deg++;
    state.byId[e.s].adj.push(state.byId[e.t]);
    state.byId[e.t].adj.push(state.byId[e.s]);
  });
  if (!state.showOrphans) {
    // drop nodes with no edges; edges only ever touch kept nodes
    state.nodes = state.nodes.filter(function (v) { return v.deg > 0; });
    state.byId = {};
    state.nodes.forEach(function (v) { state.byId[v.id] = v; });
  }
  var base = state.level === 'files' ? 4 : 2.6;
  var mult = state.level === 'files' ? 1.7 : 1.15;
  state.nodes.forEach(function (v) {
    v.r = base + Math.sqrt(v.deg) * mult;
  });
  initPositions();
  state.hover = null;
  state.selected = null;
  tip.hidden = true;
}

// deterministic initial positions: files on a circle, symbols near their
// file, everything else scattered a bit further out.
function initPositions() {
  var rnd = mulberry32(state.level === 'files' ? 1 : 2);
  var files = state.nodes.filter(function (v) { return v.kind === 'file'; });
  var nf = files.length || 1;
  var R = 80 + 26 * Math.sqrt(nf);
  files.forEach(function (f, i) {
    var a = (i / nf) * Math.PI * 2;
    f.x = R * Math.cos(a); f.y = R * Math.sin(a);
    f.vx = 0; f.vy = 0;
  });
  state.nodes.forEach(function (v) {
    if (v.kind === 'file') return;
    var host = state.byId['file:' + v.relpath];
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

// force layout (grid-binned repulsion + springs)
const CELL = 100;

function tick() {
  var n = state.nodes.length;
  if (!n) return;
  var grid = {};
  var i, v;
  for (i = 0; i < n; i++) {
    v = state.nodes[i];
    var k = Math.floor(v.x / CELL) + ',' + Math.floor(v.y / CELL);
    (grid[k] || (grid[k] = [])).push(v);
  }
  var rest = (state.level === 'files' ? 110 : 70) * state.sim.spacing;
  var kRep = state.sim.repulsion, kSpr = state.sim.spring,
      damp = state.sim.damping, center = state.sim.center;
  for (i = 0; i < n; i++) {
    v = state.nodes[i];
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
          var f = (kRep / d2) * state.alpha;
          fx += (dx / d) * f; fy += (dy / d) * f;
        }
      }
    }
    for (var ai = 0; ai < v.adj.length; ai++) {
      var o2 = v.adj[ai];
      var dx2 = o2.x - v.x, dy2 = o2.y - v.y;
      var d3 = Math.sqrt(dx2 * dx2 + dy2 * dy2) || 1;
      var f2 = (d3 - rest) * kSpr * state.alpha;
      fx += (dx2 / d3) * f2; fy += (dy2 / d3) * f2;
    }
    fx -= v.x * center * state.alpha;
    fy -= v.y * center * state.alpha;
    v.vx = (v.vx + fx) * damp;
    v.vy = (v.vy + fy) * damp;
  }
  for (i = 0; i < n; i++) {
    v = state.nodes[i];
    if (v === state.dragNode) continue;
    var sp = Math.sqrt(v.vx * v.vx + v.vy * v.vy);
    if (sp > state.sim.speed) { v.vx *= state.sim.speed / sp; v.vy *= state.sim.speed / sp; }
    v.x += v.vx; v.y += v.vy;
  }
}

export function startSim() {
  if (state.running) return;
  state.running = true;
  var step = function () {
    tick(); tick();
    draw();
    state.alpha *= state.sim.cooling;
    if (state.alpha > 0.02) {
      requestAnimationFrame(step);
    } else {
      state.running = false;
      // frame a freshly built layout — but never yank the camera
      // back after the user has been arranging nodes
      if (state.refit) { state.refit = false; fitView(); }
      draw();
    }
  };
  requestAnimationFrame(step);
}

export function reheat(a) {
  if (state.alpha < a) state.alpha = a;
  if (!state.running) startSim();
}

export function rebuild() {
  buildLevel();
  updateLegend();
  updateCounts();
  state.refit = true;
  startSim();
}
