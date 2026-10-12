// doc_maker /graph — codebase dependency graph (Obsidian-style).
//
// Entry point only. The behavior lives in the modules under web/graph/
// (dom, state, util, rng, view, draw, layout, interact, panel, search,
// controls, theme); this file wires them together and keeps the
// /graph.js URL the page template references.
//
// Vanilla JS + <canvas>, no dependencies. Data: /api/graph (meta/graph.json).
// Two levels:
//   files   — one node per file (plus modules); IMPORTS kept, CALLS re-
//             aggregated onto file→file pairs
//   symbols — one node per function/variable (plus files); CONTAINS,
//             CALLS and READS edges; ext/builtin symbols optional
// Interactions: wheel zoom, background pan, node drag (reheats layout),
// hover tooltip, click → doc opens in the left panel, a fuzzy search
// bar (path+name) that dims non-matches, right-hand menu to tune the
// force-layout parameters (repulsion, spring, …) live.
import { canvas, stage, legend, counts } from './graph/dom.js';
import { state } from './graph/state.js';
import { esc } from './graph/util.js';
import { adoptInitialSelection, init as initControls } from './graph/controls.js';
import { init as initInteract } from './graph/interact.js';
import { init as initPanel } from './graph/panel.js';
import { init as initSearch } from './graph/search.js';
import { init as initTheme } from './graph/theme.js';
import { rebuild } from './graph/layout.js';

if (canvas) {
  // order keeps the window-mousemove/mouseup listeners registered in the
  // same sequence as before: interact's, then the panel-resizer's
  adoptInitialSelection();
  initInteract();
  initControls();
  initPanel();
  initSearch();
  initTheme();

  fetch('/api/graph')
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      state.raw = data;
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
}
