// web/graph/view.js — camera/viewport: resize, world↔screen, fit, pick.

import { state } from './state.js';
import { canvas, stage } from './dom.js';

export function resize() {
  state.dpr = window.devicePixelRatio || 1;
  var w = stage.clientWidth, h = stage.clientHeight;
  var pw = Math.round(w * state.dpr), ph = Math.round(h * state.dpr);
  if (canvas.width !== pw || canvas.height !== ph) {
    canvas.width = pw;
    canvas.height = ph;
  }
}

export function worldOf(clientX, clientY) {
  var r = canvas.getBoundingClientRect();
  return {
    x: (clientX - r.left - state.view.ox) / state.view.s,
    y: (clientY - r.top - state.view.oy) / state.view.s,
  };
}

export function fitView() {
  if (!state.nodes.length) return;
  var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  state.nodes.forEach(function (v) {
    if (v.x < minx) minx = v.x;
    if (v.x > maxx) maxx = v.x;
    if (v.y < miny) miny = v.y;
    if (v.y > maxy) maxy = v.y;
  });
  var w = stage.clientWidth, h = stage.clientHeight;
  var bw = (maxx - minx) || 1, bh = (maxy - miny) || 1;
  var s = Math.min(w / (bw + 140), h / (bh + 140));
  s = Math.max(0.04, Math.min(4, s));
  state.view.s = s;
  state.view.ox = (w - (minx + maxx) * s) / 2;
  state.view.oy = (h - (miny + maxy) * s) / 2;
}

export function pick(clientX, clientY) {
  var p = worldOf(clientX, clientY);
  var best = null, bd = Infinity;
  var slack = 6 / state.view.s;
  for (var i = 0; i < state.nodes.length; i++) {
    var v = state.nodes[i];
    var dx = v.x - p.x, dy = v.y - p.y;
    var d = Math.sqrt(dx * dx + dy * dy);
    if (d < v.r + slack && d < bd) { bd = d; best = v; }
  }
  return best;
}
