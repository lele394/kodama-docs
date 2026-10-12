// Shared state + constants for the /graph page.
//
// Every other module imports this one module instance, so `state` is the
// single source of truth (the same closure the old single-file version
// had).

export const COLORS = {
  file: '#3b6fd4', function: '#2e9e63', variable: '#d98a14',
  module: '#8b5cf6', builtin: '#12a594', ext: '#d6455c',
};

export const NAMES = {
  file: 'file', function: 'function', variable: 'variable',
  module: 'module', builtin: 'builtin', ext: 'external',
};

// force-layout parameters — tunable at runtime from the right-hand menu
export const SIM_DEFAULTS = {
  repulsion: 2400,   // node-node push (kRep)
  spring: 0.08,      // edge attraction (kSpr)
  spacing: 1,        // multiplier on the level's base link distance
  center: 0.003,     // pull towards the origin
  damping: 0.8,      // velocity decay per tick
  cooling: 0.99,     // alpha decay per frame (lower = settles faster)
  speed: 30,         // max velocity per tick
};

export const state = {
  raw: null,
  level: 'files',
  showExt: false,
  showOrphans: true,
  sim: {},
  nodes: [], edges: [], byId: {},
  view: { s: 1, ox: 0, oy: 0 },
  alpha: 0, running: false,
  refit: false,
  hover: null, selected: null, dragNode: null,
  resizing: false,
  dpr: 1,
  fg: '#1f2328',
  accent: '#3b6fd4',
  docStack: [],
  // fuzzy search: query text, whether it is active (non-empty), the
  // matched node ids ({ [id]: true }) and whether the dropdown is open
  query: '',
  searchActive: false,
  matchSet: null,
  dropOpen: false,
};
Object.keys(SIM_DEFAULTS).forEach(function (k) { state.sim[k] = SIM_DEFAULTS[k]; });

export function resetSim() {
  Object.keys(SIM_DEFAULTS).forEach(function (k) { state.sim[k] = SIM_DEFAULTS[k]; });
}
