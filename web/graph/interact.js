// web/graph/interact.js — wheel zoom, background pan, node dragging,
// hover tooltip, and "click a node → open its doc".

import { state, NAMES } from './state.js';
import { canvas, tip, stage } from './dom.js';
import { pick } from './view.js';
import { draw } from './draw.js';
import { reheat } from './layout.js';
import { openNode } from './panel.js';

let drag = null;

export function init() {
  canvas.addEventListener('wheel', function (e) {
    e.preventDefault();
    var f = Math.exp(-e.deltaY * 0.0015);
    var s2 = Math.max(0.03, Math.min(10, state.view.s * f));
    f = s2 / state.view.s;
    var r = canvas.getBoundingClientRect();
    var px = e.clientX - r.left, py = e.clientY - r.top;
    state.view.ox = px - (px - state.view.ox) * f;
    state.view.oy = py - (py - state.view.oy) * f;
    state.view.s = s2;
    draw();
  }, { passive: false });

  canvas.addEventListener('mousedown', function (e) {
    // middle button is a dedicated pan: never grabs a node
    var v = (e.button === 1) ? null : pick(e.clientX, e.clientY);
    drag = {
      node: v,
      sx: e.clientX, sy: e.clientY,
      ox: state.view.ox, oy: state.view.oy,
      vx: v ? v.x : 0, vy: v ? v.y : 0,
      moved: false,
    };
    if (v) state.dragNode = v;
    canvas.style.cursor = 'grabbing';
    e.preventDefault();
  });

  window.addEventListener('mousemove', function (e) {
    if (drag) {
      var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      if (drag.node) {
        drag.node.x = drag.vx + dx / state.view.s;
        drag.node.y = drag.vy + dy / state.view.s;
        reheat(0.25);
      } else {
        state.view.ox = drag.ox + dx;
        state.view.oy = drag.oy + dy;
        draw();
      }
      return;
    }
    if (state.resizing) return;
    if (e.target !== canvas) {
      // pointer over the top bar / doc panel / menus — no hover there
      if (state.hover) { state.hover = null; tip.hidden = true; draw(); }
      return;
    }
    state.hover = pick(e.clientX, e.clientY);
    canvas.style.cursor = state.hover ? 'pointer' : 'grab';
    if (state.hover) {
      tip.hidden = false;
      tip.textContent = state.hover.label + ' — ' + NAMES[state.hover.kind]
        + (state.hover.relpath ? '  ·  ' + state.hover.relpath : '');
      var r = stage.getBoundingClientRect();
      tip.style.left = (e.clientX - r.left + 14) + 'px';
      tip.style.top = (e.clientY - r.top + 14) + 'px';
    } else {
      tip.hidden = true;
    }
    draw();
  });

  window.addEventListener('mouseup', function () {
    if (!drag) return;
    var d = drag;
    drag = null;
    state.dragNode = null;
    canvas.style.cursor = 'grab';
    if (!d.moved && d.node) openNode(d.node);
  });

  canvas.addEventListener('mouseleave', function () {
    if (drag) return;
    state.hover = null;
    tip.hidden = true;
    draw();
  });

  window.addEventListener('resize', function () { draw(); });
}
