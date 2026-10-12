// web/graph/search.js — fuzzy node search for the /graph top bar.
//
// The query is matched against each node's path+name (e.g.
// "src/test/main.lua" or "src/main.lua/foo"), not just the node's
// label. The dropdown shows the 10 best matches; picking one opens the
// node's doc in the panel and selects the node — but the query is left
// exactly as typed, so the highlighted matches stay on the canvas and
// the user can keep looking them over.

import { state, NAMES } from './state.js';
import { esc } from './util.js';
import { draw } from './draw.js';
import { openNode } from './panel.js';

const DROP_CAP = 10;
// a match starting at these positions counts as "at a word boundary"
const BOUNDARY = ' /._-';

// Fuzzy subsequence score; higher is better, -1 means no match.
// Rewards consecutive runs, matches starting at a word boundary
// (string start or right after a / . _ - character) and full
// substring hits. Deterministic: same query + same node set gives the
// same ranking.
export function fuzzyScore(query, text) {
  var q = query.toLowerCase(), t = text.toLowerCase();
  if (!q.length) return 0;
  var score = 0, ti = 0, i, j, gap;
  for (i = 0; i < q.length; i++) {
    j = t.indexOf(q[i], ti);
    if (j === -1) return -1;
    gap = j - ti;
    if (gap === 0) score += 3;
    else score += Math.max(0.25, 1.5 - gap * 0.1);
    if (j === 0 || BOUNDARY.indexOf(t[j - 1]) !== -1) score += 4;
    ti = j + 1;
  }
  var sub = t.indexOf(q);
  if (sub !== -1) score += 20 + q.length * 2 + (sub === 0 ? 6 : 0);
  return score;
}

// what a query is matched against: the node's path+name
function haystack(v) {
  if (v.name) return (v.relpath ? v.relpath + '/' : '') + v.name;
  return v.relpath || v.label || v.id;
}

// score every current node; null when the query is empty
export function scoreAll(query) {
  var q = String(query == null ? '' : query).trim();
  if (!q) return null;
  var out = [];
  for (var i = 0; i < state.nodes.length; i++) {
    var v = state.nodes[i];
    var s = fuzzyScore(q, haystack(v));
    if (s >= 0) out.push({ v: v, s: s, i: i });
  }
  out.sort(function (a, b) { return (b.s - a.s) || (a.i - b.i); });
  return out;
}

function hideDrop() {
  state.dropOpen = false;
  var drop = document.getElementById('search-drop');
  if (drop) drop.hidden = true;
}

function renderDrop(matched) {
  state.dropOpen = true;
  var drop = document.getElementById('search-drop');
  if (!drop) return;
  if (!matched.length) {
    drop.innerHTML = '<div class="sd-empty">no nodes match</div>';
    drop.hidden = false;
    return;
  }
  drop.innerHTML = matched.slice(0, DROP_CAP)
    .map(function (m) {
      return '<div class="sd-row" data-id="' + esc(m.v.id) + '">'
        + '<span class="sd-name">' + esc(m.v.label) + '</span>'
        + '<span class="sd-kind">' + esc(NAMES[m.v.kind] || m.v.kind)
        + '</span>'
        + (m.v.relpath
           ? '<span class="sd-path">' + esc(m.v.relpath) + '</span>'
           : '')
        + '</div>';
    }).join('');
  drop.hidden = false;
}

// Recompute the match set for the given query and redraw.
// `open` = the user is typing right now: force the dropdown visible.
// Called without it (e.g. after a level rebuild) the dropdown only
// updates while it is already open — it never pops up on its own.
export function applySearch(query, open) {
  state.query = String(query == null ? '' : query);
  var matched = scoreAll(state.query);
  if (matched) {
    state.searchActive = true;
    var set = {};
    matched.forEach(function (m) { set[m.v.id] = true; });
    state.matchSet = set;
    if (open || state.dropOpen) renderDrop(matched);
  } else {
    state.searchActive = false;
    state.matchSet = null;
    hideDrop();
  }
  draw();
}

function pickRow(rowEl) {
  var id = rowEl.getAttribute ? rowEl.getAttribute('data-id') : null;
  var v = id ? state.byId[id] : null;
  if (!v) return;
  hideDrop();
  // select the node + open its doc; the query stays in the search bar
  openNode(v);
}

export function init() {
  var wrap = document.getElementById('graph-search-wrap');
  var input = document.getElementById('graph-search');
  if (!wrap || !input) return;
  var drop = document.getElementById('search-drop');

  input.addEventListener('input', function () {
    applySearch(input.value, true);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      var first = drop ? drop.querySelector('.sd-row') : null;
      if (first) { e.preventDefault(); pickRow(first); }
    } else if (e.key === 'Escape') {
      hideDrop();
    }
  });

  drop.addEventListener('click', function (e) {
    var row = (e.target && e.target.closest)
      ? e.target.closest('.sd-row') : null;
    if (row) pickRow(row);
  });

  // click anywhere outside the search box dismisses the dropdown —
  // the query (and the matching highlight) is kept
  document.addEventListener('mousedown', function (e) {
    if (!state.dropOpen) return;
    if (e.target && wrap.contains && wrap.contains(e.target)) return;
    hideDrop();
  });
}
