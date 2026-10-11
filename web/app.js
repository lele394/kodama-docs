// doc_maker theme switcher: toggles light/dark, remembers the choice.
(function () {
  'use strict';
  var KEY = 'doc_maker_theme';
  var link = document.getElementById('doc-theme');
  var btn = document.getElementById('theme-toggle');
  if (!link || !btn) return;

  function current() {
    var m = link.getAttribute('href').match(/\/theme\/(light|dark)\//);
    return m ? m[1] : 'light';
  }

  function apply(name) {
    link.setAttribute('href', '/theme/' + name + '/style.css');
    btn.textContent = name === 'dark' ? '\u263E dark' : '\u2600 light';
  }

  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  apply(saved === 'dark' || saved === 'light' ? saved : current());

  btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    apply(next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
  });
})();
