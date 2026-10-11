// web/graph/panel.js — the left-hand documentation panel: load a node's
// doc into it, walk links, go back.

import { state, NAMES } from './state.js';
import {
  panelBody, panelTitle, panelBack, panelOpen,
} from './dom.js';
import { draw } from './draw.js';
import { esc, sanitize } from './util.js';

const docStack = [];

function urlFor(v) {
  if (v.kind === 'file') {
    return { url: '/files/' + v.relpath + '.md', frag: null };
  }
  if (v.kind === 'function') {
    return {
      url: '/files/' + v.relpath + '.md',
      frag: 'fn-' + sanitize(v.name) + '-' + v.line,
    };
  }
  if (v.kind === 'variable') {
    return { url: '/files/' + v.relpath + '.md', frag: 'variables' };
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
      // t.url is an absolute path, so any origin serves to resolve the
      // relative links it contains; a fixed one keeps this location-
      // independent.
      var ORIGIN = 'http://docmaker.local';
      var base = new URL(ORIGIN + t.url);
      var bodyEl = doc.body;
      Array.prototype.forEach.call(bodyEl.querySelectorAll('a[href]'),
        function (a) {
          var href = a.getAttribute('href');
          if (!href) return;
          if (href.charAt(0) === '#') {
            a.setAttribute('data-doc-frag', href.slice(1));
            a.removeAttribute('href');
            return;
          }
          var abs;
          try { abs = new URL(href, base).href; } catch (err) { return; }
          var hash = abs.indexOf('#');
          var path = hash >= 0 ? abs.slice(0, hash) : abs;
          var pathOnly = path.indexOf(ORIGIN) === 0
            ? path.slice(ORIGIN.length) : path;
          if (pathOnly.indexOf('/files/') === 0
              && pathOnly.slice(-3) === '.md') {
            a.setAttribute('data-doc-url', '/' + pathOnly.slice(1));
            if (hash >= 0) a.setAttribute('data-doc-frag', abs.slice(hash + 1));
            a.removeAttribute('href');
          } else {
            a.setAttribute('href', abs);
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
