// doc_maker theme switcher: toggles light/dark. The choice is persisted
// by the server (POST /api/theme -> web/theme_state.json), so it survives
// reloads and applies to every browser — no per-browser localStorage.
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

  function current() {
    var m = link.getAttribute('href').match(/\/theme\/(light|dark)\//);
    return m ? m[1] : 'light';
  }

  function apply(name) {
    link.setAttribute('href', '/theme/' + name + '/style.css');
    btn.textContent = name === 'dark' ? '\u263E dark' : '\u2600 light';
    if (hljsLight && hljsDark) {
      hljsLight.disabled = name !== 'light';
      hljsDark.disabled = name !== 'dark';
    }
  }

  // The server already rendered the page with the persisted theme; this
  // only makes sure the button label matches.
  apply(current());

  btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    apply(next);
    fetch('/api/theme', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: next,
    }).catch(function () {
      /* offline — the choice still applies to this page */
    });
  });
})();
