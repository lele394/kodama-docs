// web/graph/draw.js — canvas rendering + the legend/counts readout.

import { state, COLORS, NAMES } from './state.js';
import { canvas, ctx, legend, counts } from './dom.js';
import { resize } from './view.js';

const EDGE_STYLE = {
  CALLS: { color: 'rgba(110,120,140,0.55)', dash: [], width: 1.2 },
  IMPORTS: { color: 'rgba(59,111,212,0.55)', dash: [6, 4], width: 1.2 },
  CONTAINS: { color: 'rgba(110,120,140,0.30)', dash: [], width: 1 },
  READS: { color: 'rgba(217,138,20,0.65)', dash: [3, 3], width: 1.1 },
  BRIDGES: { color: 'rgba(18,165,148,0.80)', dash: [2, 3], width: 1.7 },
  EXPORTS: { color: 'rgba(139,92,246,0.65)', dash: [4, 3], width: 1.3 },
};

const EDGE_LABELS = {
  CALLS: 'calls', IMPORTS: 'imports', CONTAINS: 'contains',
  READS: 'reads', BRIDGES: 'bridges', EXPORTS: 'exports',
};
const EDGE_ORDER = ['CALLS', 'IMPORTS', 'CONTAINS', 'READS',
                    'BRIDGES', 'EXPORTS'];

// rgba(...) with a different alpha; handles the styles above and falls back
// to the original string for anything unexpected.
function withAlpha(color, alpha) {
  var m = /^rgba?\(([^)]+)\)$/.exec(String(color));
  if (!m) return color;
  var p = m[1].split(',').map(function (x) { return x.trim(); });
  return 'rgba(' + p[0] + ',' + p[1] + ',' + p[2] + ',' + alpha + ')';
}

const MUTED_EDGE = {};
Object.keys(EDGE_STYLE).forEach(function (t) {
  MUTED_EDGE[t] = withAlpha(EDGE_STYLE[t].color, 0.09);
});

// low-alpha versions of the node colors — used to dim nodes that do
// NOT match the active search query, so the matches stand out
function toRgba(hex, a) {
  return 'rgba(' + parseInt(hex.slice(1, 3), 16) + ','
    + parseInt(hex.slice(3, 5), 16) + ',' + parseInt(hex.slice(5, 7), 16)
    + ',' + a + ')';
}
const MUTED = {};
Object.keys(COLORS).forEach(function (k) { MUTED[k] = toRgba(COLORS[k], 0.12); });
const MUTED_FALLBACK = 'rgba(150,150,150,0.15)';

// Nodes/edges that stay lit while a search is active: every fuzzy match,
// plus the selected node (clicking a result should keep its context).
function searchFocus() {
  if (!state.searchActive || !state.matchSet) return null;
  var focus = {};
  for (var id in state.matchSet) focus[id] = true;
  if (state.selected) focus[state.selected.id] = true;
  return focus;
}

function strokeEdges(list, color, width, dash) {
  if (!list.length) return;
  ctx.beginPath();
  list.forEach(function (e) {
    var a = state.byId[e.s], b = state.byId[e.t];
    if (!a || !b) return;
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.setLineDash(dash || []);
  ctx.stroke();
}

export function draw() {
  if (!state.raw) return;
  resize();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(
    state.dpr * state.view.s, 0, 0, state.dpr * state.view.s,
    state.dpr * state.view.ox, state.dpr * state.view.oy
  );

  // edges, batched per style for speed
  var focus = searchFocus();
  var groups = {};
  state.edges.forEach(function (e) {
    (groups[e.type] || (groups[e.type] = [])).push(e);
  });

  // While searching, edges that do not touch a match (or the selected
  // node) fade into the background; the rest keep their normal style.
  if (focus) {
    Object.keys(groups).forEach(function (t) {
      var st = EDGE_STYLE[t] || EDGE_STYLE.CALLS;
      var dim = [], keep = [];
      groups[t].forEach(function (e) {
        if (focus[e.s] || focus[e.t]) keep.push(e);
        else dim.push(e);
      });
      strokeEdges(dim, MUTED_EDGE[t] || MUTED_EDGE.CALLS, 0.8, st.dash);
      groups[t] = keep;
    });
  }
  Object.keys(groups).forEach(function (t) {
    var st = EDGE_STYLE[t] || EDGE_STYLE.CALLS;
    strokeEdges(groups[t], st.color, st.width, st.dash);
  });
  ctx.setLineDash([]);

  // nodes — non-matching ones are dimmed while a search is active
  var searching = !!focus;
  for (var i = 0; i < state.nodes.length; i++) {
    var v = state.nodes[i];
    ctx.beginPath();
    ctx.arc(v.x, v.y, v.r, 0, Math.PI * 2);
    ctx.fillStyle = (searching && !focus[v.id])
      ? (MUTED[v.kind] || MUTED_FALLBACK)
      : (COLORS[v.kind] || '#999');
    ctx.fill();
  }

  // hover / selection rings
  [state.hover, state.selected].forEach(function (v) {
    if (!v) return;
    ctx.beginPath();
    ctx.arc(v.x, v.y, v.r + 3, 0, Math.PI * 2);
    ctx.strokeStyle = v === state.selected ? state.accent : 'rgba(30,35,45,0.6)';
    ctx.lineWidth = 2 / state.view.s;
    ctx.stroke();
  });

  // labels: zoomed in, hubs, or the hovered/selected node
  var fs = 11 / state.view.s;
  ctx.font = '500 ' + fs + 'px "Segoe UI", system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = state.fg;
  var showAll = state.view.s > 1.6;
  var hubDeg = state.level === 'files' ? 20 : 25;
  for (var j = 0; j < state.nodes.length; j++) {
    var w = state.nodes[j];
    var emph = w === state.hover || w === state.selected;
    if (emph || showAll || w.deg >= hubDeg) {
      // dimmed nodes keep their labels only when hovered/selected
      if (searching && !focus[w.id] && !emph) continue;
      ctx.fillText(w.label, w.x, w.y + w.r + fs * 1.1);
    }
  }
}

export function updateLegend() {
  var kinds = {};
  state.nodes.forEach(function (v) { kinds[v.kind] = 1; });
  var parts = Object.keys(kinds)
    .map(function (k) {
      return '<span class="lg"><i style="background:' + COLORS[k] + '"></i>'
        + NAMES[k] + 's</span>';
    });

  var edgeKinds = {};
  state.edges.forEach(function (e) { edgeKinds[e.type] = 1; });
  EDGE_ORDER.forEach(function (t) {
    if (!edgeKinds[t]) return;
    var st = EDGE_STYLE[t] || EDGE_STYLE.CALLS;
    var lineStyle = t === 'READS' ? 'dotted'
      : (st.dash && st.dash.length ? 'dashed' : 'solid');
    parts.push(
      '<span class="lg lg-edge"><i class="line" style="border-top-color:'
      + withAlpha(st.color, 0.9) + ';border-top-style:' + lineStyle
      + '"></i>' + EDGE_LABELS[t] + '</span>');
  });
  legend.innerHTML = parts.join('');
}

export function updateCounts() {
  counts.textContent = state.nodes.length + ' nodes · ' + state.edges.length + ' edges';
}
