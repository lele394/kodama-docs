// web/graph/panel.js — the left-hand documentation panel: load a node's
// doc into it, walk links, go back.

import { state, NAMES } from './state.js';
import {
  panelBody, panelTitle, panelBack, panelOpen,
} from './dom.js';
import { draw } from './draw.js';
import { esc, sanitize } from './util.js';

const docStack = [];

// Static-site mode (see STATIC_SITE.md): pages are the generated
// <base>files/<rel>.html files, fetched whole (there is no /page/ body
// endpoint) with the <main class="page"> body extracted below.
const STATIC = typeof window !== 'undefined' &&
  typeof window.__KODAMA_BASE__ === 'string';
const BASE = STATIC ? window.__KODAMA_BASE__ : '';
const docUrl = relpath => STATIC
  ? BASE + 'files/' + relpath + '.html'
  : '/files/' + relpath + '.md';

function urlFor(v) {
  if (v.kind === 'file') {
    return { url: docUrl(v.relpath), frag: null };
  }
  if (v.kind === 'function') {
    return { url: docUrl(v.relpath),
             frag: 'fn-' + sanitize(v.name) + '-' + v.line };
  }
  if (v.kind === 'variable') {
    return { url: docUrl(v.relpath), frag: 'variables' };
  }
  return null;
}

function infoCard(v) {
  return '<h1>' + esc(v.label) + '</h1>'
    + '<p>' + NAMES[v.kind] + ' symbol — no documentation page.</p>'
    + (v.relpath ? '<p>Referenced from <code>' + esc(v.relpath) + '</code></p>' : '')
    + '<p class="panel-hint">These are external or built-in names the codebase '
    + 'calls but does not define; show/hide them with the '
    + '"external symbols" toggle.</p>';
}

function afterHtml(html, title) {
  panelBody.innerHTML = html;
  panelTitle.textContent = title || '';
  panelBody.scrollTop = 0;
  if (window.hljs && window.hljs.highlightAll) {
    try { window.hljs.highlightAll(); } catch (err) { /* ignore */ }
  }
}

function loadDoc(t, frag) {
  if (panelOpen) panelOpen.hidden = false;
  afterHtml('<p class="panel-hint">loading…</p>', t.url);
  // body-only endpoint so the panel doesn't embed the page shell
  // server: the body-only endpoint, so the panel doesn't embed the page
  // shell; static: the generated .html page itself (the <main class="page">
  // body is extracted below)
  var fetchUrl = t.url.indexOf('/files/') === 0
    ? '/page' + t.url
    : t.url;
  fetch(fetchUrl)
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    })
    .then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var bodyEl = doc.querySelector('main.page') || doc.body;
      var ORIGIN = 'http://kodama-docs.local';
      var base = STATIC
        // t.url is relative to the graph page; the links inside resolve
        // against the page they belong to.
        ? new URL(t.url, location.href).href
        // server: t.url is an absolute path; any origin serves to resolve
        // its relative links — a fixed one stays location-independent.
        : new URL(ORIGIN + t.url).href;
      Array.prototype.forEach.call(bodyEl.querySelectorAll('a[href]'),
        function (a) {
          var href = a.getAttribute('href');
          if (!href) return;
          if (href.charAt(0) === '#') {
            a.setAttribute('data-doc-frag', href.slice(1));
            a.removeAttribute('href');
            return;
          }
          var u;
          try { u = new URL(href, base); } catch (err) { return; }
          var hash = u.href.indexOf('#');
          if (STATIC) {
            // internal doc page = a /files/... .html page of this site
            if (u.pathname.indexOf('/files/') >= 0
                && u.pathname.slice(-5) === '.html') {
              a.setAttribute('data-doc-url',
                hash >= 0 ? u.href.slice(0, hash) : u.href);
              if (hash >= 0)
                a.setAttribute('data-doc-frag', u.href.slice(hash + 1));
              a.removeAttribute('href');
            } else {
              a.setAttribute('href', u.href);
              a.setAttribute('target', '_blank');
            }
            return;
          }
          var pathOnly = u.pathname.indexOf(ORIGIN) === 0
            ? u.pathname.slice(ORIGIN.length) : u.pathname;
          if (pathOnly.indexOf('/files/') === 0
              && pathOnly.slice(-3) === '.md') {
            a.setAttribute('data-doc-url', '/' + pathOnly.slice(1));
            if (hash >= 0) a.setAttribute('data-doc-frag', u.href.slice(hash + 1));
            a.removeAttribute('href');
          } else {
            a.setAttribute('href', u.href);
            a.setAttribute('target', '_blank');
          }
        });
      var h1 = bodyEl.querySelector('h1');
      panelBody.innerHTML = bodyEl.innerHTML;
      panelTitle.textContent = h1 ? h1.textContent : t.url;
      if (window.hljs && window.hljs.highlightAll) {
        try { window.hljs.highlightAll(); } catch (err) { /* ignore */ }
      }
      if (frag) {
        var el = panelBody.querySelector('#' + CSS.escape(frag));
        if (el) el.scrollIntoView();
      } else {
        panelBody.scrollTop = 0;
      }
    })
    .catch(function (err) {
      afterHtml(
        '<p class="panel-err">Could not load ' + esc(t.url) + ' ('
        + esc(err && err.message || err) + '). '
        + '<a href="' + esc(t.url) + '" target="_blank">open in a tab</a></p>',
        t.url
      );
    });
}

export function openNode(v) {
  state.selected = v;
  draw();
  var t = urlFor(v);
  if (!t) {
    docStack.length = 0;
    panelBack.hidden = true;
    if (panelOpen) panelOpen.hidden = true;
    afterHtml(infoCard(v), NAMES[v.kind]);
    return;
  }
  docStack.length = 1;
  docStack[0] = t;
  panelBack.hidden = true;
  loadDoc(t, t.frag);
}

export function init() {
  panelBody.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a') : null;
    if (!a) return;
    var frag = a.getAttribute('data-doc-frag');
    var docUrl = a.getAttribute('data-doc-url');
    if (docUrl) {
      // a link to another doc page (optionally with an anchor)
      e.preventDefault();
      var t = { url: docUrl };
      docStack.push(t);
      if (docStack.length > 25) docStack.shift();
      panelBack.hidden = false;
      loadDoc(t, frag || null);
      return;
    }
    if (frag) {
      // an in-page anchor
      e.preventDefault();
      var el = panelBody.querySelector('#' + CSS.escape(frag));
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  });

  panelBack.addEventListener('click', function () {
    if (docStack.length > 1) {
      docStack.pop();
      loadDoc(docStack[docStack.length - 1], null);
    }
  });

  if (panelOpen) panelOpen.addEventListener('click', function () {
    var top = docStack[docStack.length - 1];
    if (!top) return;
    window.open(top.url + (top.frag ? '#' + top.frag : ''), '_blank',
                'noopener');
  });
}
