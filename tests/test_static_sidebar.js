// tests/test_static_sidebar.js — guard tests for the STATIC mode of the
// docs sidebar (web/sidebar.js), i.e. the window.__KODAMA_BASE__ switch
// described in STATIC_SITE.md.
//
// With the flag set to '../' (a files/ page one level below the site
// root), every href and the data URL must be base-prefixed and use .html
// targets, and the current-page detection must work off .html paths.
// The companion test_sidebar_manual.js covers the server mode (no flag);
// together the two pin down both branches.
//
// Runs on Node with a minimal DOM stub — no test framework, no browser:
//   node tests/test_static_sidebar.js

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
    // a real DOM splices a fragment's children in, not the fragment itself
    if (child.tagName === '#FRAGMENT') {
      for (const c of child.children.slice()) this.appendChild(c);
      return this;
    }
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

// we are on a files/ page under a host subpath (GitHub-Pages-style)
globalThis.location = { pathname: '/site/files/a.html', search: '' };

const store = new Map();
globalThis.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};

// THE switch: set before the import so the module top level sees it
globalThis.window = { __KODAMA_BASE__: '../' };

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

// --------------------------------------------------------------- tests
async function main() {
  const mod = await import('../web/sidebar.js');

  // the switch is on
  assert(mod.symbolsUrl === '../symbols.json',
         'symbols fetch target is base-prefixed (../symbols.json)');

  // one file, one function, one variable
  mod.data.files = [{
    relpath: 'a',
    lines: 10,
    functions: [{ name: 'go', qualified: 'go', line: 4 }],
    vars: [{ name: 'X', line: 1 }],
  }];

  const c = globalThis.document.createElement('div');
  mod.renderTree(c);

  // index row: base-prefixed .html, not /index.md
  const idx = c.children[0];
  assert(idx.href === '../index.html', 'index row -> ../index.html');

  // current page: detectCurrent() ran at import on /site/files/a.html
  // (file rows are <div> sb-file with an <a> inside)
  const fileRow = find(c, 'sb-file');
  assert(has(fileRow, 'current'),
         'current file detected from the .html pathname');
  const link = fileRow.children.find(n => n.tagName === 'A');
  assert(link && link.href === '../files/a.html',
         'file link -> ../files/a.html (base-prefixed .html)');

  // symbol rows: anchors composed on the .html file href
  const kids = fileRow.nextElementSibling;
  assert(kids && kids.children.length === 2,
         'symbol container holds the function + variable rows');
  assert(kids.children[0].href === '../files/a.html#fn-go-4',
         'function anchor on the .html href');
  assert(kids.children[1].href === '../files/a.html#variables',
         'variables anchor on the .html href');

  // manual group: .html targets, base-prefixed; current = .html path
  mod.data.manual = [
    { rel: '00 - Home.md', title: 'Home', dir: '',
      href: 'manual/00 - Home.md' },
    { rel: '01 - Getting Started/01 - Install.md', title: 'Install',
      dir: '01 - Getting Started',
      href: 'manual/01 - Getting Started/01 - Install.md' },
  ];
  globalThis.location.pathname =
      '/site/manual/01%20-%20Getting%20Started/01%20-%20Install.html';
  const mc = globalThis.document.createElement('div');
  mod.renderManualGroup(mc);
  const rows = [];
  (function collect(n) {
    for (const ch of n.children) { rows.push(ch); collect(ch); }
  })(mc);
  const home = rows.find(n => has(n, 'sb-file') &&
                             n.href === '../manual/00 - Home.html');
  const install = rows.find(n => has(n, 'sb-file') &&
                                n.href !== '../manual/00 - Home.html');
  assert(home && home.href === '../manual/00 - Home.html',
         'manual root page -> ../manual/00 - Home.html');
  assert(install.href ===
         '../manual/01 - Getting Started/01 - Install.html',
         'manual page -> base-prefixed .html');
  assert(has(install, 'current') && !has(home, 'current'),
         'current manual page detected from the .html pathname');

  console.log('ok   static mode: base-prefixed .html hrefs everywhere');
  console.log('ok   static mode: current-page detection on .html paths');
  console.log('\nstatic-sidebar tests passed');
}

main().catch(err => { console.error(err); process.exit(1); });
