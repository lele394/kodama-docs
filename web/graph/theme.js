// web/graph/theme.js — theme-aware colors (--fg / --accent) + live switch
// when the theme link's href changes.

import { state } from './state.js';
import { themeLink } from './dom.js';
import { draw } from './draw.js';

function refreshTheme() {
  var cs = getComputedStyle(document.body);
  state.fg = cs.getPropertyValue('--fg').trim() || state.fg;
  state.accent = cs.getPropertyValue('--accent').trim() || state.accent;
  if (state.raw) draw();
}

export function init() {
  if (themeLink && 'MutationObserver' in window) {
    new MutationObserver(refreshTheme).observe(themeLink, {
      attributes: true, attributeFilter: ['href'],
    });
  }
  // pick up the active theme's colors on load (the observer only fires
  // when the theme link changes)
  refreshTheme();
}
