// web/sidebar.js — docs-mode sidebar: a collapsible file hierarchy plus
// a filterable fuzzy search over files, functions and variables.
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
// Search grammar (tokens are whitespace-separated, combined with AND):
//   word                 fuzzy-match a symbol/file's own name
//   @fn  @var            type filter: functions / variables only
//   @file                type filter: files only
//   @fn:con              fuzzy-match function names matching "con"
//   @var:i               fuzzy-match variable names matching "i"
//   @file:src            a path scope: matches files under ~src, and (when
//                        combined with a symbol type) restricts that type to
//                        files under ~src
// So "@file:src @var:i" = variables named ~i in files under ~src. Plain words and typed filters freely mix.
// Results are grouped by file; the search query is carried in the URL
// (?q=…) so clicking a result opens the target without clearing the box.
//
// File-row click: on the page of a file, clicking its name toggles the
// node open/closed (no reload, scroll position kept); elsewhere it
// navigates and expands. The chevron always just toggles.
//
// Per-node expansion and the sidebar width are per-browser UI preferences,
// so they live in localStorage — unlike the theme, which is a server-wide
// choice persisted in web/theme_state.json. The sidebar itself is always
// visible (it is a permanent, resizable part of the docs layout).
//
// All names are inserted with textContent (no innerHTML), so symbol
// names can never inject markup.

import { fuzzyScore } from './fuzzy.js';
import { sanitize } from './graph/util.js';

const LS_EXPAND = 'kodama.sidebar.expand';
const LS_WIDTH = 'kodama.sidebar.width';
const SEARCH_CAP = 50;
const MIN_W = 200;
const MAX_W = 640;

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
let currentQuery = '';      // live search text (carried in the URL)

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

// A file row. Clicking the name (or the row body) is "smart":
//   - on this file's own page  -> toggle open/closed, no reload
//   - any other page           -> expand (persist) + navigate
// The chevron always just toggles.
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
  row.addEventListener('click', e => {
    if (current === rp) {
      e.preventDefault();      // stay on this page, just toggle
      toggleRow(row);
    } else {
      expanded.add(id);        // open it once we land there
      saveExpanded();
      if (e.target !== a) {    // row body: navigate manually
        e.preventDefault();
        location.href = a.href;
      }
      // e.target === a: let the anchor navigate (with our saved expansion)
    }
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

  renderManualGroup(container);

  const root = buildTree();
  renderNode(container, root, '');
}

// section 0: the user's hand-written docs, right under the index row.
// Always open, no expandable children (the pages are flat).
function renderManualGroup(container) {
  const pages = data.manual || [];
  if (!pages.length) return;
  const hdr = el('div', 'sb-row sb-dir sb-manual-hdr');
  hdr.appendChild(el('span', 'sb-tw', '📚'));
  hdr.appendChild(el('span', 'sb-name', 'Manual'));
  hdr.appendChild(el('span', 'sb-count', String(pages.length)));
  container.appendChild(hdr);
  const cp = decodeURIComponent(location.pathname);
  pages.forEach(p => {
    const label = p.title || base(p.rel);
    const row = el('a',
      'sb-row sb-file' + (cp === '/' + p.href ? ' current' : ''));
    row.href = '/' + p.href;
    row.appendChild(el('span', 'sb-tw', ''));
    row.appendChild(el('span', 'sb-name',
                       p.dir ? (p.dir + ' / ' + label) : label));
    container.appendChild(row);
  });
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
  (data.manual || []).forEach(p => {
    const label = p.title || base(p.rel);
    cands.push({ kind: 'file', label: label,
                 text: label + ' ' + p.rel,
                 href: '/' + p.href, path: p.rel, order: cands.length });
  });
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
                   href: varHref(rp), path: rp,
                   order: cands.length }));
  }
}

// Parse the query into constraint tokens. Each token is
//   { type: 'file'|'fn'|'var'|null, query: string }
// A null type is a plain (untyped) word. A token with an empty query is
// a bare type filter (e.g. "@fn").
const TYPE_ALIASES = {
  file: 'file', fn: 'fn', func: 'fn', function: 'fn', functions: 'fn',
  var: 'var', variable: 'var', variables: 'var',
};
function parseQuery(q) {
  const tokens = [];
  for (const raw of String(q).trim().split(/\s+/)) {
    if (!raw) continue;
    if (raw[0] === '@') {
      const m = raw.match(/^@([A-Za-z]+)(?::([\s\S]+))?$/);
      if (m) {
        const t = TYPE_ALIASES[m[1].toLowerCase()];
        if (t) { tokens.push({ type: t, query: m[2] || '' }); continue; }
      }
      const word = raw.slice(1);
      if (word) tokens.push({ type: null, query: word });
    } else {
      tokens.push({ type: null, query: raw });
    }
  }
  return tokens;
}

// Score one candidate against every token; -1 means it cannot satisfy
// the constraint set. A typed token matches the candidate's own field
// when the types agree, and a "@file:" token scopes by the parent path.
function scoreCandidate(c, tokens) {
  let total = 0;
  for (const tk of tokens) {
    let s;
    if (tk.type === null || tk.type === c.kind) {
      s = fuzzyScore(tk.query, c.text);
      if (c.kind === 'fn' && c.qtext)
        s = Math.max(s, fuzzyScore(tk.query, c.qtext));
    } else if (tk.type === 'file') {
      if (!tk.query) return -1;   // bare "@file" filters to files, never a scope
      s = fuzzyScore(tk.query, c.path);
    } else {
      return -1;   // e.g. an @fn constraint cannot match a variable
    }
    if (s < 0) return -1;
    total += s;
  }
  return total;
}

function rankCandidates(tokens) {
  const out = [];
  for (const c of cands) {
    const s = scoreCandidate(c, tokens);
    if (s >= 0) out.push({ c: c, s: s });
  }
  out.sort((a, b) => (b.s - a.s) || (a.c.order - b.c.order));
  return out.slice(0, SEARCH_CAP);
}

// Group ranked hits by their file so the results read as file > symbols.
const KIND_ORDER = { fn: 0, var: 1, file: 2 };
function groupByFile(hits) {
  const groups = new Map();
  for (const h of hits) {
    let g = groups.get(h.c.path);
    if (!g) { g = { rp: h.c.path, fileHit: null, syms: [] };
              groups.set(h.c.path, g); }
    if (h.c.kind === 'file') g.fileHit = h;
    else g.syms.push(h);
  }
  for (const g of groups.values())
    g.syms.sort((a, b) => (b.s - a.s)
      || (KIND_ORDER[a.c.kind] - KIND_ORDER[b.c.kind])
      || (a.c.label < b.c.label ? -1 : 1));
  const best = g => Math.max(
    g.fileHit ? g.fileHit.s : -1,
    ...g.syms.map(h => h.s));
  return Array.from(groups.values())
    .sort((a, b) => (best(b) - best(a)) || (a.rp < b.rp ? -1 : 1));
}

// Carry the live query into a result link so clicking it keeps the search.
function withQ(href) {
  if (!currentQuery) return href;
  const i = href.indexOf('#');
  const path = i >= 0 ? href.slice(0, i) : href;
  const hash = i >= 0 ? href.slice(i) : '';
  return path + '?q=' + encodeURIComponent(currentQuery) + hash;
}

function renderSearch(container, q) {
  container.textContent = '';
  const tokens = parseQuery(q);
  const hits = tokens.length ? rankCandidates(tokens) : [];
  if (!hits.length) {
    container.appendChild(el('div', 'sb-empty', 'no matches for "' + q + '"'));
    return;
  }
  const groups = groupByFile(hits);
  container.appendChild(el('div', 'sb-hint',
    hits.length + ' match' + (hits.length === 1 ? '' : 'es') +
    ' in ' + groups.length + ' file' + (groups.length === 1 ? '' : 's') +
    ' — Enter opens the first'));
  for (const g of groups) {
    const hdr = el('a', 'sb-row sb-group');
    hdr.href = (g.fileHit && g.fileHit.c.href)
        ? withQ(g.fileHit.c.href) : withQ(fileHref(g.rp));
    hdr.appendChild(el('span', 'sb-tw', ''));
    hdr.appendChild(el('span', 'sb-name', g.rp));
    hdr.appendChild(el('span', 'sb-kind', 'file'));
    container.appendChild(hdr);
    if (g.syms.length) {
      const kids = el('div', 'sb-kids sb-results');
      for (const h of g.syms) {
        const a = el('a', 'sb-row sb-hit');
        a.href = withQ(h.c.href);
        a.appendChild(el('span', 'sb-tw', ''));
        a.appendChild(el('span', 'sb-name', h.c.label));
        a.appendChild(el('span', 'sb-kind', h.c.kind));
        kids.appendChild(a);
      }
      container.appendChild(kids);
    }
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

// -------------------------------------------------------------- resizer
function initResizer(aside) {
  const rz = aside.querySelector('.sb-resizer');
  if (!rz) return;
  try {
    const saved = localStorage.getItem(LS_WIDTH);
    if (saved) aside.style.width = saved;
  } catch (e) { /* ignore */ }

  let dragging = false, startX = 0, startW = 0;
  rz.addEventListener('pointerdown', e => {
    dragging = true;
    startX = e.clientX;
    startW = aside.getBoundingClientRect().width;
    try { rz.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    document.body.classList.add('sb-resizing');
    rz.classList.add('active');
  });
  rz.addEventListener('pointermove', e => {
    if (!dragging) return;
    const w = Math.max(MIN_W, Math.min(MAX_W, startW + (e.clientX - startX)));
    aside.style.width = w + 'px';
  });
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove('sb-resizing');
    rz.classList.remove('active');
    try { localStorage.setItem(LS_WIDTH, aside.style.width); } catch (e) { /* ignore */ }
  };
  rz.addEventListener('pointerup', stop);
  rz.addEventListener('pointercancel', stop);
}

// ----------------------------------------------------------------- init
function init() {
  const aside = document.getElementById('sidebar');
  const input = document.getElementById('sb-search');
  treeEl = document.getElementById('sb-tree');
  if (!aside || !input || !treeEl) return;

  initResizer(aside);

  // restore a query carried in the URL (?q=…) — e.g. after clicking a hit
  let initialQ = '';
  try {
    initialQ = (new URLSearchParams(location.search).get('q')) || '';
  } catch (e) { /* ignore */ }
  currentQuery = initialQ;
  input.value = initialQ;

  // fetch the index, then draw
  fetch('/api/symbols', { credentials: 'same-origin' })
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(src => {
      data.files = Array.isArray(src.files) ? src.files : [];
      data.manual = Array.isArray(src.manual) ? src.manual : [];
      loadExpanded();
      buildCandidates();
      if (currentQuery) renderSearch(treeEl, currentQuery);
      else renderTree(treeEl);
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
  const updateURLQuery = q => {
    try {
      const u = new URL(location.href);
      if (q) u.searchParams.set('q', q); else u.searchParams.delete('q');
      history.replaceState(null, '', u);
    } catch (e) { /* ignore */ }
  };
  input.addEventListener('input', () => {
    const q = String(input.value || '').trim();
    currentQuery = q;
    updateURLQuery(q);
    if (q) renderSearch(treeEl, q);
    else renderTree(treeEl);
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const a = treeEl.querySelector('a.sb-hit')
            || treeEl.querySelector('a.sb-group');
      if (a) location.href = a.getAttribute('href');
    } else if (e.key === 'Escape') {
      input.value = '';
      currentQuery = '';
      updateURLQuery('');
      renderTree(treeEl);
      input.blur();
    }
  });

  // "/" focuses the search box (unless the user is typing somewhere)
  document.addEventListener('keydown', e => {
    if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = document.activeElement;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    e.preventDefault();
    input.focus();
    input.select();
  });
}

init();
