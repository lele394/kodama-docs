// tests/test_sidebar_manual.js — guard tests for the manual group in the
// docs sidebar (web/sidebar.js).
//
// The manual sits at the top of the sidebar (right under the index row)
// and must behave exactly like the generated directories: the "Manual"
// header is collapsible, every manual sub-folder is a collapsible node,
// and the folder hierarchy of the manual is preserved (Manual > folder
// > page). The group is open by default, and landing on a manual page
// forces its folder chain open even if the saved state has it closed.
//
// Runs on Node with a minimal DOM stub — no test framework, no browser:
//   node tests/test_sidebar_manual.js

'use strict';

// ---------------------------------------------------------------- stubs
class SNode {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.className = '';
    this.children = [];
    this.parentNode = null;
    this.attrs = {};
    this.listeners = {};
    this.hidden = false;
    this.style = {};
    this.href = '';
    this._text = '';
  }
  appendChild(child) {
    if (child.parentNode)
      child.parentNode.children
          .splice(child.parentNode.children.indexOf(child), 1);
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  click() { for (const fn of this.listeners.click || []) fn({ preventDefault() {} }); }
  get nextElementSibling() {
    if (!this.parentNode) return null;
    const i = this.parentNode.children.indexOf(this);
    return this.parentNode.children[i + 1] || null;
  }
  querySelector(sel) {
    const cls = sel.replace(/^\./, '');
    const walk = n => {
      for (const c of n.children) {
        if (String(c.className).split(/\s+/).includes(cls)) return c;
        const r = walk(c);
        if (r) return r;
      }
      return null;
    };
    return walk(this);
  }
  get classList() {
    const self = this;
    return { contains: c => String(self.className).split(/\s+/).includes(c) };
  }
  get textContent() { return this._text; }
  set textContent(v) { this._text = v == null ? '' : String(v); this.children = []; }
}

globalThis.document = {
  createElement: t => new SNode(t),
  createDocumentFragment: () => new SNode('#fragment'),
  getElementById: () => null,   // sidebar.js init() bails out early
  addEventListener: () => {},
};

globalThis.location = { pathname: '/', search: '' };

const store = new Map();
globalThis.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};

// ------------------------------------------------------------- helpers
const has = (n, cls) => String(n.className).split(/\s+/).includes(cls);
function find(node, cls) {
  for (const c of node.children) {
    if (has(c, cls)) return c;
    const r = find(c, cls);
    if (r) return r;
  }
  return null;
}
function assert(cond, msg) {
  if (!cond) { console.error('ASSERT FAILED: ' + msg); process.exit(1); }
}

// ------------------------------------------------------------- fixture
// Payload shape matches manual_payload() in kodama_docs/manual.py, with a
// root page, a flat folder, and a two-level folder chain.
const MANUAL = [
  { rel: '00 - Home.md', title: 'Home', dir: '',
    href: 'manual/00 - Home.md' },
  { rel: '01 - Getting Started/01 - Install.md', title: 'Install',
    dir: '01 - Getting Started',
    href: 'manual/01 - Getting Started/01 - Install.md' },
  { rel: '01 - Getting Started/02 - First run.md', title: 'First run',
    dir: '01 - Getting Started',
    href: 'manual/01 - Getting Started/02 - First run.md' },
  { rel: '02 - How It Works/01 - The Pipeline/overview.md', title: 'Overview',
    dir: '02 - How It Works/01 - The Pipeline',
    href: 'manual/02 - How It Works/01 - The Pipeline/overview.md' },
];

// --------------------------------------------------------------- tests
function test_tree_built_from_folder_paths(mod) {
  const t = mod.buildManualTree();
  assert(t.pages.length === 1 && t.pages[0].rel === '00 - Home.md',
         'root page (00 - Home) lives directly under the Manual group');
  assert(Object.keys(t.children).sort().join(' ') ===
         '01 - Getting Started 02 - How It Works',
         'top-level folders preserved');
  const flat = t.children['01 - Getting Started'];
  assert(flat.pages.length === 2, 'flat folder keeps its two pages');
  const hw = t.children['02 - How It Works'];
  assert(hw.pages.length === 0 &&
         Object.keys(hw.children).join(' ') === '01 - The Pipeline',
         'nested folder chain preserved (How It Works > The Pipeline)');
  assert(hw.children['01 - The Pipeline'].pages.length === 1,
         'leaf page under the nested folder');
  assert(mod.countManualPages(t) === 4, 'group count = 4 pages');
  assert(mod.countManualPages(hw) === 1, 'nested folder count = 1 page');
  console.log('ok   test_tree_built_from_folder_paths');
}

function test_default_expanded_opens_manual(mod) {
  const empty = { children: {}, files: [] };
  const s = mod.defaultExpanded(empty);
  assert(s.has('manual'), 'Manual header open by default');
  assert(s.has('manual/01 - Getting Started'), 'flat folder open by default');
  assert(s.has('manual/02 - How It Works'), 'nested parent open by default');
  assert(s.has('manual/02 - How It Works/01 - The Pipeline'),
         'nested child open by default');
  console.log('ok   test_default_expanded_opens_manual');
}

function render(mod) {
  const c = globalThis.document.createElement('div');
  mod.renderManualGroup(c);
  return c;
}

function test_render_manual_group_hierarchical(mod) {
  store.set('kodama.sidebar.expand', JSON.stringify({
    ids: ['manual', 'manual/01 - Getting Started',
          'manual/02 - How It Works', 'manual/02 - How It Works/01 - The Pipeline'],
  }));
  mod.loadExpanded();

  const c = render(mod);
  assert(c.children.length === 2, 'header row + one kids container');
  const [hdr, kids] = c.children;
  assert(has(hdr, 'sb-manual-hdr') && has(hdr, 'sb-dir'),
         'header keeps the manual styling and is a dir row');
  assert(hdr.getAttribute('data-id') === 'manual', 'header expansion id');
  assert((hdr.listeners.click || []).length === 1, 'header is clickable');
  assert(!kids.hidden, 'group visible when expanded');
  const tw = hdr.querySelector('.sb-tw');
  assert(tw && tw.textContent === '▾', 'open chevron on the header');
  const name = hdr.children[1];
  assert(name && /Manual/.test(name.textContent), 'header labelled "Manual"');
  const count = hdr.children[2];
  assert(count && count.textContent === '4', 'header badge = page count');

  // folder rows first (sorted), then the root-level pages
  const [f1, f1k, f2, f2k, home] = kids.children;
  assert(has(f1, 'sb-dir') && f1.getAttribute('data-id') ===
         'manual/01 - Getting Started', 'folder row 1 (collapsible)');
  assert(has(f2, 'sb-dir') && f2.getAttribute('data-id') ===
         'manual/02 - How It Works', 'folder row 2 (collapsible)');
  assert(has(home, 'sb-file') && home.href === '/manual/00 - Home.md',
         'root page link after the folders');
  assert(home.children[1].textContent === 'Home', 'root page shows its title');

  // flat folder -> its two pages
  const [in1, in2] = f1k.children;
  assert(has(in1, 'sb-file') && in1.href ===
         '/manual/01 - Getting Started/01 - Install.md', 'page under folder 1');
  assert(in1.children[1].textContent === 'Install', 'page label = title');
  assert(has(in2, 'sb-file') && in2.href ===
         '/manual/01 - Getting Started/02 - First run.md', 'second page');

  // nested folder -> sub-folder -> page
  const [nf, nfk] = f2k.children;
  assert(has(nf, 'sb-dir') && nf.getAttribute('data-id') ===
         'manual/02 - How It Works/01 - The Pipeline', 'nested dir row');
  assert(has(nfk.children[0], 'sb-file') && nfk.children[0].href ===
         '/manual/02 - How It Works/01 - The Pipeline/overview.md',
         'leaf page link at full depth');
  console.log('ok   test_render_manual_group_hierarchical');
}

function test_toggle_collapses_and_persists(mod) {
  const c = render(mod);
  const [hdr, kids] = c.children;
  hdr.click();
  assert(kids.hidden, 'clicking the header collapses the group');
  assert(!mod.expanded.has('manual'), 'collapse persisted to the state set');
  assert(hdr.querySelector('.sb-tw').textContent === '▸', 'chevron flipped');
  hdr.click();
  assert(!kids.hidden, 'clicking again re-opens the group');
  assert(mod.expanded.has('manual'), 're-open persisted to the state set');
  console.log('ok   test_toggle_collapses_and_persists');
}

function test_landing_on_manual_page_forces_chain_open(mod) {
  // saved state has the manual collapsed; the browser delivers the
  // pathname percent-encoded
  store.set('kodama.sidebar.expand', JSON.stringify({
    ids: ['kodama_docs'],
  }));
  globalThis.location.pathname =
    '/manual/02%20-%20How%20It%20Works/01%20-%20The%20Pipeline/overview.md';
  mod.loadExpanded();
  assert(mod.expanded.has('manual'), 'header forced open');
  assert(mod.expanded.has('manual/02 - How It Works'), 'parent forced open');
  assert(mod.expanded.has('manual/02 - How It Works/01 - The Pipeline'),
         'leaf folder forced open');
  assert(!mod.expanded.has('manual/01 - Getting Started'),
         'unrelated folders stay as saved');
  console.log('ok   test_landing_on_manual_page_forces_chain_open');
}

function test_current_manual_page_highlighted(mod) {
  store.set('kodama.sidebar.expand', JSON.stringify({
    ids: ['manual', 'manual/01 - Getting Started'],
  }));
  globalThis.location.pathname =
    '/manual/01%20-%20Getting%20Started/01%20-%20Install.md';
  mod.loadExpanded();
  const c = render(mod);
  const cur = find(c, 'current');
  assert(cur, 'exactly one page row is current');
  assert(cur.href === '/manual/01 - Getting Started/01 - Install.md',
         'current row is the page being viewed');
  console.log('ok   test_current_manual_page_highlighted');
}

function test_empty_manual_renders_nothing(mod) {
  mod.data.manual = [];
  const c = render(mod);
  assert(c.children.length === 0, 'no manual group without pages');
  mod.data.manual = MANUAL;   // restore for any later test
  console.log('ok   test_empty_manual_renders_nothing');
}

async function main() {
  const mod = await import('../web/sidebar.js');
  mod.data.manual = MANUAL;
  test_tree_built_from_folder_paths(mod);
  test_default_expanded_opens_manual(mod);
  test_render_manual_group_hierarchical(mod);
  test_toggle_collapses_and_persists(mod);
  test_landing_on_manual_page_forces_chain_open(mod);
  test_current_manual_page_highlighted(mod);
  test_empty_manual_renders_nothing(mod);
  console.log('\n7 sidebar-manual tests passed');
}

main().catch(err => { console.error(err); process.exit(1); });
