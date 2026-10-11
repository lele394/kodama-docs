// web/graph/controls.js — the top bar (level radios, ext/orphan toggles,
// reset), the panel resizer strip, and the layout-parameters menu.

import { state, resetSim } from './state.js';
import {
  extChk, extInput, orphanInput,
} from './dom.js';
import { draw } from './draw.js';
import { fitView } from './view.js';
import { rebuild, reheat } from './layout.js';

export function adoptInitialSelection() {
  // The browser restores the radio/checkbox state from before a refresh;
  // adopt it so the loaded level always matches the visible selection.
  var _levels = document.querySelectorAll('input[name=level]');
  for (var _i = 0; _i < _levels.length; _i++) {
    if (_levels[_i].checked) { state.level = _levels[_i].value; break; }
  }
  state.showExt = extInput.checked;
  state.showOrphans = orphanInput.checked;
  extInput.disabled = (state.level === 'files');
  extChk.classList.toggle('disabled', state.level === 'files');
}

export function init() {
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
  resizer.addEventListener('mousedown', function (e) {
    state.resizing = true;
    resizer.classList.add('active');
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
  window.addEventListener('mousemove', function (e) {
    if (!state.resizing) return;
    var w = Math.max(PANEL_MIN, Math.min(PANEL_MAX, Math.round(e.clientX)));
    if (panelEl.style.width !== (w + 'px')) {
      panelEl.style.width = w + 'px';
      draw();
    }
  });
  window.addEventListener('mouseup', function () {
    if (!state.resizing) return;
    state.resizing = false;
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
      state.level = r.value;
      extInput.disabled = (state.level === 'files');
      extChk.classList.toggle('disabled', state.level === 'files');
      rebuild();
    });
  });

  extInput.addEventListener('change', function (e) {
    state.showExt = e.target.checked;
    if (state.level === 'symbols') rebuild();
  });

  orphanInput.addEventListener('change', function (e) {
    state.showOrphans = e.target.checked;
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
      paramsSliders.querySelector('#in-' + d.key).value = state.sim[d.key];
      paramsSliders.querySelector('#val-' + d.key).textContent = state.sim[d.key];
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
      state.sim[d.key] = parseFloat(e.target.value);
      paramsSliders.querySelector('#val-' + d.key).textContent = state.sim[d.key];
      reheat(0.6);
    });
  });
  syncSliders();

  paramsToggle.addEventListener('click', function () {
    paramsEl.hidden = !paramsEl.hidden;
  });
  paramsReset.addEventListener('click', function () {
    resetSim();
    syncSliders();
    reheat(0.6);
  });
}
