// web/graph/util.js — small shared helpers (no state, no DOM).

// make a name safe for use in a URL fragment / CSS id
export function sanitize(name) {
  return String(name).replace(/[^A-Za-z0-9._@-]/g, '_');
}

// escape a string for innerHTML
export function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}

// node ids: file:{rp} | fn:{rp}::{name}@{line} | var:{rp}::{name}@{line}
export function relpathOf(id) {
  if (id.indexOf('file:') === 0) return id.slice(5);
  var c = id.indexOf(':');
  var d = id.indexOf('::');
  return id.slice(c + 1, d);
}

export function fileOf(id) { return 'file:' + relpathOf(id); }

// display label: a file's basename, a symbol's own name
export function labelOf(n) {
  if (n.kind === 'file') {
    var p = n.relpath;
    var i = p.lastIndexOf('/');
    return i >= 0 ? p.slice(i + 1) : p;
  }
  return n.name || n.id;
}
