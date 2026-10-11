// web/graph/dom.js — the DOM elements the graph page uses, resolved once.
//
// `canvas` is null when this file runs on a page without the graph
// (the entry module checks and does nothing in that case).

function el(id) { return document.getElementById(id); }

export const canvas = el('graph-canvas');
export const ctx = canvas ? canvas.getContext('2d') : null;
export const stage = el('graph-stage');
export const tip = el('graph-tip');
export const legend = el('graph-legend');
export const counts = el('graph-counts');
export const panelBody = el('panel-body');
export const panelTitle = el('panel-title');
export const panelBack = el('panel-back');
export const panelOpen = el('panel-open');
export const extChk = el('ext-chk');
export const extInput = el('show-ext');
export const orphanInput = el('show-orphans');
export const themeLink = el('doc-theme');
