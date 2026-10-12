// web/sidebar.js — docs-mode sidebar: a collapsible file hierarchy plus
// a fuzzy search over files, functions and variables.
//
// Data: GET /api/symbols — a slim index of meta/symbols.json (files ->
// functions/variables with name + line; function bodies are not sent).
//
// The tree mirrors the docs layout: directory groups > files > that
// file's functions (badge "fn") and file-level variables (badge "var").
// Every row navigates to the matching anchor:
//   files      /files/<relpath>.md
//   functions  /files/<relpath>.md#fn-<name>-<line>
//   variables  /files/<relpath>.md#variables   (the variables table)
//
// Typing in the search box switches the tree to a ranked flat list of
// fuzzy matches (the same scorer as the /graph bar, web/fuzzy.js);
// clearing the box restores the tree. "/" focuses the box, Enter opens
// the first hit, Escape clears.
//
// The open/closed state and per-node expansion are per-browser UI
// preferences, so they live in localStorage — unlike the theme, which
// is a server-wide choice persisted in web/theme_state.json.
//
// All names are inserted with textContent (no innerHTML), so symbol
// names can never inject markup.

import { fuzzyScore } from './fuzzy.js';
import { sanitize } from './graph/util.js';

const LS_OPEN = 'kodama.sidebar.open';
const LS_EXPAND = 'kodama.sidebar.expand';
const SEARCH_CAP = 50;
const MOBILE = 860;

// ---------------------------------------------------------------- helpers
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function base(rp) {
  const i = String(rp || '').lastIndexOf('/');
  return i >= 0 ? String(rp).slice(i + 1) : String(rp);
}

const fileHref = rp => '/files/' + rp + '.md';
const fnHref = (rp, name, line) =>
  fileHref(rp) + '#fn-' + sanitize(name) + '-' + line;
const varHref = rp => fileHref(rp) + '#variables';

// relpath of the page we are on, or 'index', or null
function detectCurrent() {
  let p = decodeURIComponent(location.pathname);
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
  if (p === '/' || p === '/index.md') return 'index';
  if (p.startsWith('/files/') && p.endsWith('.md'))
    return p.slice('/files/'.length, -3);
  return null;
}

// --------------------------------------------------------------- state
const data = { files: [] };
const current = detectCurrent();
let expanded = new Set();   // dir:<path> | file:<relpath>
let cands = [];             // precomputed search candidates
let treeEl = null;

// ------------------------------------------------------------ rendering
// build a nested tree of the files: node = {name, children: {name: node},
// files: [relpath]}
function buildTree() {
  const root = { children: {}, files: [] };
  for (const f of data.files) {
    const parts = f.relpath.split('/');
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i];
      if (!node.children[p])
        node.children[p] = { name: p, children: {}, files: [] };
      node = node.children[p];
    }
    node.files.push(f.relpath);
  }
  return root;
}

function countFiles(node) {
  let n = node.files.length;
  for (const k in node.children) n += countFiles(node.children[k]);
  return n;
}

function fileByRelpath(rp) {
  for (const f of data.files) if (f.relpath === rp) return f;
  return null;
}

function toggleRow(row) {
  const kids = row.nextElementSibling;
  if (!kids || !kids.classList.contains('sb-kids')) return;
  const nowOpen = kids.hidden;
  kids.hidden = !nowOpen;
  const tw = row.querySelector('.sb-tw');
  if (tw) tw.textContent = nowOpen ? '▾' : '▸';
  const id = row.getAttribute('data-id');
  if (id) {
    if (nowOpen) expanded.add(id); else expanded.delete(id);
    saveExpanded();
  }
}

function dirRow(id, name, count) {
  const row = el('div', 'sb-row sb-dir');
  row.setAttribute('data-id', id);
  row.appendChild(el('span', 'sb-tw', expanded.has(id) ? '▾' : '▸'));
  row.appendChild(el('span', 'sb-name', name));
  row.appendChild(el('span', 'sb-count', String(count)));
  row.addEventListener('click', () => toggleRow(row));
  return row;
}

function fileRow(rp, count) {
  const id = 'file:' + rp;
  const row = el('div',
    'sb-row sb-file' + (current === rp ? ' current' : ''));
  row.setAttribute('data-id', id);
  const tw = el('span', 'sb-tw', expanded.has(id) ? '▾' : '▸');
  const a = el('a', 'sb-name', base(rp));
  a.href = fileHref(rp);
  const ct = count ? el('span', 'sb-count', String(count)) : null;
  row.appendChild(tw);
  row.appendChild(a);
  if (ct) row.appendChild(ct);
  tw.addEventListener('click', e => {
    e.preventDefault();
    e.stopPropagation();
    toggleRow(row);
  });
  // clicking the row background also opens the file
  row.addEventListener('click', e => {
    if (e.target === a) return;   // the anchor navigates itself
    e.preventDefault();
    location.href = a.href;
  });
  return row;
}

function symbolRows(rp, f) {
  const frag = document.createDocumentFragment();
  const mk = (href, name, kind) => {
    const a = el('a', 'sb-row sb-sym');
    a.href = href;
    a.appendChild(el('span', 'sb-tw', ''));
    a.appendChild(el('span', 'sb-name', name));
    a.appendChild(el('span', 'sb-kind', kind));
    return a;
  };
  (f.functions || []).forEach(fn =>
    frag.appendChild(mk(fnHref(rp, fn.name, fn.line), fn.name, 'fn')));
  (f.vars || []).forEach(v =>
    frag.appendChild(mk(varHref(rp), v.name, 'var')));
  return frag;
}

// render the directory/file tree into `container`
function renderTree(container) {
  container.textContent = '';
  // the index page first — always present
  const idx = el('a', 'sb-row' + (current === 'index' ? ' current' : ''));
  idx.href = '/index.md';
  idx.appendChild(el('span', 'sb-tw', ''));
  idx.appendChild(el('span', 'sb-name', 'index'));
  idx.appendChild(el('span', 'sb-kind', 'md'));
  container.appendChild(idx);

  const root = buildTree();
  renderNode(container, root, '');
}

function renderNode(container, node, path) {
  // sub-directories first, then the files that live in this directory
  const names = Object.keys(node.children).sort();
  for (const name of names) {
    const id = path ? path + '/' + name : name;
    const child = node.children[name];
    const row = dirRow(id, name, countFiles(child));
    container.appendChild(row);
    const kids = el('div', 'sb-kids');
    renderNode(kids, child, id);
    kids.hidden = !expanded.has(id);
    container.appendChild(kids);
  }
  const files = node.files.slice().sort();
  for (const rp of files) {
    const f = fileByRelpath(rp);
    const count = ((f && f.functions) || []).length +
                  ((f && f.vars) || []).length;
    container.appendChild(fileRow(rp, count));
    const kids = el('div', 'sb-kids');
    if (f) kids.appendChild(symbolRows(rp, f));
    kids.hidden = !expanded.has('file:' + rp);
    container.appendChild(kids);
  }
}

// ---------------------------------------------------------------- search
function buildCandidates() {
  cands = [];
  for (const f of data.files) {
    const rp = f.relpath;
    cands.push({ kind: 'file', label: base(rp), text: rp,
                 href: fileHref(rp), path: rp, order: cands.length });
    (f.functions || []).forEach(fn =>
      cands.push({ kind: 'fn', label: fn.name, text: fn.name,
                   qtext: fn.qualified || '',
                   href: fnHref(rp, fn.name, fn.line), path: rp,
                   order: cands.length }));
    (f.vars || []).forEach(v =>
      cands.push({ kind: 'var', label: v.name, text: v.name,
                   href: varHref(rp), path: rp, order: cands.length }));
  }
}

function search(q) {
  const out = [];
  for (const c of cands) {
    let s = fuzzyScore(q, c.text);
    if (c.qtext) s = Math.max(s, fuzzyScore(q, c.qtext));
    if (s >= 0) out.push({ c: c, s: s });
  }
  out.sort((a, b) => (b.s - a.s) || (a.c.order - b.c.order));
  return out.slice(0, SEARCH_CAP);
}

function renderSearch(container, q) {
  container.textContent = '';
  const hits = search(q);
  if (!hits.length) {
    container.appendChild(
      el('div', 'sb-empty', 'no matches for "' + q + '"'));
    return;
  }
  container.appendChild(el('div', 'sb-hint',
    hits.length + ' match' + (hits.length === 1 ? '' : 'es') +
    ' — Enter opens the first'));
  for (const h of hits) {
    const a = el('a', 'sb-row sb-hit');
    a.href = h.c.href;
    a.appendChild(el('span', 'sb-kind', h.c.kind));
    a.appendChild(el('span', 'sb-name', h.c.label));
    if (h.c.path !== h.c.label)
      a.appendChild(el('span', 'sb-path', h.c.path));
    container.appendChild(a);
  }
}

// ------------------------------------------------------------ expansion
function defaultExpanded(root) {
  // all directory groups open; the current file (if any) open
  const s = new Set();
  (function walk(node, path) {
    for (const k in node.children) {
      const id = path ? path + '/' + k : k;
      s.add(id);
      walk(node.children[k], id);
    }
  })(root, '');
  if (current && current !== 'index') s.add('file:' + current);
  return s;
}

function saveExpanded() {
  try {
    localStorage.setItem(LS_EXPAND, JSON.stringify({
      ids: Array.from(expanded),
    }));
  } catch (e) { /* private mode — state just won't persist */ }
}

function loadExpanded() {
  let saved = null;
  try {
    const obj = JSON.parse(localStorage.getItem(LS_EXPAND) || 'null');
    if (obj && Array.isArray(obj.ids)) saved = new Set(obj.ids);
  } catch (e) { /* ignore */ }
  if (saved) {
    expanded = saved;
    // force the current file's chain open — the user is on that page
    if (current && current !== 'index') {
      const parts = current.split('/');
      let p = '';
      for (let i = 0; i < parts.length - 1; i++) {
        p = p ? p + '/' + parts[i] : parts[i];
        expanded.add(p);
      }
      expanded.add('file:' + current);
    }
  } else {
    expanded = defaultExpanded(buildTree());
  }
  saveExpanded();
}

// ----------------------------------------------------------------- init
function init() {
  const aside = document.getElementById('sidebar');
  const input = document.getElementById('sb-search');
  treeEl = document.getElementById('sb-tree');
  const btn = document.getElementById('sidebar-toggle');
  if (!aside || !input || !treeEl) return;

  // open/closed state (per browser)
  let savedOpen = null;
  try { savedOpen = localStorage.getItem(LS_OPEN); } catch (e) { /* ignore */ }
  const open = savedOpen == null
    ? window.innerWidth >= MOBILE
    : savedOpen === '1';
  const setOpen = o => {
    document.body.classList.toggle('sb-closed', !o);
    try { localStorage.setItem(LS_OPEN, o ? '1' : '0'); } catch (e) { /* ignore */ }
  };
  setOpen(open);
  if (btn) btn.addEventListener('click', () => {
    const next = document.body.classList.contains('sb-closed');
    setOpen(next);
    if (next && document.activeElement !== input) input.focus();
  });

  // fetch the index, then draw
  fetch('/api/symbols', { credentials: 'same-origin' })
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(src => {
      data.files = Array.isArray(src.files) ? src.files : [];
      loadExpanded();
      buildCandidates();
      renderTree(treeEl);
      // scroll the current file into view if the tree is long
      const cr = treeEl.querySelector('.sb-file.current');
      if (cr && cr.scrollIntoView)
        cr.scrollIntoView({ block: 'nearest' });
    })
    .catch(err => {
      treeEl.textContent = '';
      treeEl.appendChild(el('div', 'sb-empty',
        'no symbol index (run the pipeline first)'));
    });

  // search box
  input.addEventListener('input', () => {
    const q = String(input.value || '').trim();
    if (q) renderSearch(treeEl, q);
    else renderTree(treeEl);
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const a = treeEl.querySelector('a.sb-hit');
      if (a) location.href = a.getAttribute('href');
    } else if (e.key === 'Escape') {
      input.value = '';
      renderTree(treeEl);
      input.blur();
    }
  });

  // "/" focuses the search box (unless the user is typing somewhere)
  document.addEventListener('keydown', e => {
    if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = document.activeElement;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    if (document.body.classList.contains('sb-closed')) return;
    e.preventDefault();
    input.focus();
    input.select();
  });
}

init();
