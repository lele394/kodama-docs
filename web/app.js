// kodama-docs theme switcher: toggles light/dark.
// --serve: the choice is persisted by the server (POST /api/theme ->
// web/theme_state.json), so it survives reloads and applies to every
// browser — no per-browser localStorage.
// static site (see STATIC_SITE.md): there is no server, so the choice is
// persisted per browser in localStorage and the baked-in default comes
// from the generated page.
(function () {
  'use strict';
  // The vendored highlight.js build does not auto-initialize: highlight
  // the code blocks ourselves (safe to call twice — already-highlighted
  // elements are skipped).
  if (window.hljs && window.hljs.highlightAll) {
    window.hljs.highlightAll();
  }
  var link = document.getElementById('doc-theme');
  var btn = document.getElementById('theme-toggle');
  if (!link || !btn) return;
  var hljsLight = document.getElementById('hljs-light');
  var hljsDark = document.getElementById('hljs-dark');

  var STATIC = typeof window.__KODAMA_BASE__ === 'string';
  var BASE = STATIC ? window.__KODAMA_BASE__ : '';
  var LS_THEME = 'kodama.theme';

  function current() {
    var m = link.getAttribute('href').match(/theme\/(light|dark)\//);
    return m ? m[1] : 'light';
  }

  function apply(name) {
    link.setAttribute('href', BASE + 'theme/' + name + '/style.css');
    if (hljsLight && hljsDark) {
      hljsLight.disabled = name !== 'light';
      hljsDark.disabled = name !== 'dark';
    }
    btn.textContent = name === 'dark' ? '\u263E dark' : '\u2600 light';
  }

  if (STATIC) {
    // honor a previous choice on this browser, else the baked-in default
    var saved = null;
    try { saved = localStorage.getItem(LS_THEME); } catch (err) { /* file:// */ }
    if (saved === 'light' || saved === 'dark') apply(saved);
  }
  // the page already carries the active theme (server-persisted or the
  // generator's default) — make sure the button label matches
  apply(current());

  btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    apply(next);
    if (STATIC) {
      try { localStorage.setItem(LS_THEME, next); } catch (err) { /* file:// */ }
      return;
    }
    fetch(BASE + '/api/theme', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: next,
    }).catch(function () {
      /* offline — the choice still applies to this page */
    });
  });
})();
