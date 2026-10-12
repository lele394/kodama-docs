// web/fuzzy.js — fuzzy subsequence scorer shared by the /graph search bar
// (web/graph/search.js) and the docs sidebar (web/sidebar.js).
//
// Pure function, no DOM, no dependencies.

// a match starting at these positions counts as "at a word boundary"
export const BOUNDARY = ' /._-';

// Fuzzy subsequence score; higher is better, -1 means no match.
// Rewards consecutive runs, matches starting at a word boundary
// (string start or right after a / . _ - character) and full
// substring hits. Deterministic: same query + same text gives the
// same score.
export function fuzzyScore(query, text) {
  var q = String(query == null ? '' : query).toLowerCase();
  var t = String(text == null ? '' : text).toLowerCase();
  if (!q.length) return 0;
  var score = 0, ti = 0, i, j, gap;
  for (i = 0; i < q.length; i++) {
    j = t.indexOf(q[i], ti);
    if (j === -1) return -1;
    gap = j - ti;
    if (gap === 0) score += 3;
    else score += Math.max(0.25, 1.5 - gap * 0.1);
    if (j === 0 || BOUNDARY.indexOf(t[j - 1]) !== -1) score += 4;
    ti = j + 1;
  }
  var sub = t.indexOf(q);
  if (sub !== -1) score += 20 + q.length * 2 + (sub === 0 ? 6 : 0);
  return score;
}
