# Static site generation (no server needed)

Goal: make `kodama-docs` able to emit a **self-contained static site** — plain
HTML/CSS/JS files that work when hosted anywhere, including **GitHub Pages**,
or opened straight from disk. No server, no build step, no third-party web
tooling.

## 1. Why this is not free today

The current web UI is server-centric. Every moving part assumes the built-in
`main.py --serve` (stdlib `http.server`) is running:

| Concern | How it works under `--serve` | Problem for a static site |
| --- | --- | --- |
| Pages | `.md` rendered to HTML **on demand**; absolute paths in the shell (`/theme/…`, `/lib/…`, `/app.js`, `/sidebar.js`, brand → `/index.md`) | absolute paths break under a subpath (`user.github.io/repo/`) and under `file://` |
| Sidebar data | `fetch('/api/symbols')` — a slim index the server builds from `meta/symbols.json` + `meta/manual.json` | no `/api/*` without a server |
| Graph view | `fetch('/api/graph')` → `meta/graph.json`; the left panel fetches **bodies only** from `/page/<rel>` | no endpoints; a full page fetch would embed the whole shell |
| Theme | server-side: choice POSTed to `/api/theme`, persisted in `web/theme_state.json`, applied to **every** browser | no endpoint; persistence must move to the browser |
| Manual assets | raw bytes served from `manual/` (images, css) | must be copied into the site |
| Cross links | markdown links stay relative (`../foo.md`) and resolve because the server serves the same tree | links must point at the generated `.html` files |

`sidebar.js`, `graph.js` and the `graph/*` modules are **ES modules** — they
load fine on any http(s) origin (GitHub Pages included) but not from
`file://` (browser CORS on module scripts) — and their data comes from
`fetch()`, which browsers also block on `file://`. The static build therefore
emits the two entry points as **bundled classic scripts** (see §2) and
**inlines the data into the pages**, so even the sidebar/search/graph work
straight from disk. (Solved in milestone 5; this doc reflects the final
behaviour.)

## 2. Design

One new flag:

```
python main.py --config <cfg> --static
```

runs the normal pipeline (cached → cheap) and then builds a self-contained
folder **`<output_dir>/site/`**:

```
site/
  index.html                 # from index.md
  files/<relpath>.html       # one per source file (from files/<relpath>.md)
  manual/<relpath>.html      # hand-written manual pages (from manual/<relpath>.md)
  manual/…                   # non-markdown manual files, copied verbatim
  graph.html                 # the graph view (from web/templates/graph.html)
  404.html                   # GitHub Pages-friendly, links back to index.html
  app.js                     # copied from web/ (already a classic IIFE)
  sidebar.js                 # BUNDLE: web/sidebar.js + every module it imports
  graph.js                   # inlined into one classic, file://-safe script
                             # (fuzzy.js and graph/* ship INSIDE the bundles)
  lib/highlight.min.js  lib/github*.min.css  lib/LICENSE
  theme/light/style.css  theme/dark/style.css     (from web/themes/)
  icon/icon.ico  icon/icon.png                    (from the repo-root icon/)
  symbols.json                 # the /api/symbols payload, prebuilt (slim index)
  graph.json                   # copy of meta/graph.json
```

The site root mirrors the server's URL space 1:1 — `/app.js`, `/theme/…`,
`/symbols.json` become `site/app.js`, `site/theme/…`, `site/symbols.json` —
so the same templates and the same JS work in both modes; only the relative
prefix differs. (The server maps `/theme/*` to `web/themes/*` on disk, hence
the singular `theme/` in the static layout.)

**The `file://` fix — classic bundles + inline data.** Browsers refuse both
external ES-module scripts *and* `fetch()` of local files under `file://`, so
the static builder does two more things the server never does:

1. **Bundles the two entry points.** `kodama_docs/js_bundle.py` inlines every
   module `sidebar.js` / `graph.js` imports (depth-first, cycle-checked, and
   only the relative-import + named-export subset that `web/` actually uses —
   anything else, like default imports or re-exports, fails the build
   loudly) and rewrites `import`/`export` onto a tiny
   `__kodama_define` / `__kodama_require` registry, yielding one
   self-contained classic script per entry point. The `web/` sources stay ES
   modules; the server still serves them natively over http — the bundler
   only runs at static-build time.
2. **Inlines the data into the pages.** Every page gets
   `window.__KODAMA_SYMBOLS__ = <slim index>`; `graph.html` gets
   `window.__KODAMA_GRAPH__ = <graph data>`. The JSON is emitted compact with
   `</` escaped to `<\/` so it can never terminate its own `<script>`.
   `sidebar.js` / `graph.js` prefer the inline value and fall back to
   `fetch(<base>symbols.json)` / `fetch(<base>graph.json)` — the path a
   server or a non-inline context takes. `symbols.json` / `graph.json` are
   still written to the site, so the fallback and direct links keep working.

Key decisions:

- **Relative paths, computed per page depth.** `index.html` and `graph.html`
  use the site root directly; `files/a.html` uses `../`; `manual/x/y.html`
  uses `../../`. The generator already knows each page's depth. Works at any
  host subpath and from `file://`.
- **One template, two modes.** `web/templates/page.html` / `graph.html`
  become base-aware: every absolute `/…` asset/link becomes `{base}…`, and
  the server passes `base='/'` (behaviour unchanged) while the static
  builder passes the depth-relative base.
- **Data inlined, with file fallback.** `symbols.json` (same slim shape the
  server's `/api/symbols` returns) and `graph.json` are written at the site
  root at build time — and *also* inlined into the pages as
  `window.__KODAMA_SYMBOLS__` / `window.__KODAMA_GRAPH__`, because `file://`
  forbids the fetch. The JS prefers the inline copy and falls back to
  `fetch(<base>symbols.json)` / `fetch(<base>graph.json)`.
- **Static-mode switch in JS: `window.__KODAMA_BASE__`.** The generator
  injects `<script>window.__KODAMA_BASE__ = "<base>"</script>` before the
  page scripts. Its presence = static mode:
  - `sidebar.js` — data from `window.__KODAMA_SYMBOLS__` (inline; `fetch`
    of `<base>symbols.json` only as fallback); rows link to
    `<base>files/<rel>.html`, `<base>index.html`,
    `<base>manual/…` (`.md` → `.html`); current-page detection handles
    `.html` and host subpaths.
  - `app.js` — theme persists to `localStorage` instead of
    `POST /api/theme`; initial theme is whatever the generator baked in
    (from `web/web_settings.yaml` / `web/theme_state.json`).
  - `graph.js` — data from `window.__KODAMA_GRAPH__` (inline; `fetch` of
    `<base>graph.json` only as fallback).
  - `graph/panel.js` — `urlFor()` targets `<base>files/<rel>.html`;
    `loadDoc()` fetches that page and extracts the rendered body
    (`<main class="page">`) instead of calling `/page/<rel>`; internal
    doc links are recognized by `files/… + .html`.
  - Under `--serve` the flag is absent → every existing URL/endpoint path
    is taken; the server is byte-for-byte as it is today.
- **Link rewriting, build-time only.** Rendered bodies keep their relative
  markdown links; the static builder rewrites *internal* `href="….md"` to
  `….html` (absolute `http(s)`/`mailto:`/`#` targets untouched). Server
  rendering is untouched.
- **No new dependencies.** Generation is plain Python (stdlib + what the
  pipeline already uses); the JS reuses the exact files under `web/`.

## 3. Files touched

| File | Change |
| --- | --- |
| `kodama_docs/static_site.py` | **new** — `build(cfg)`: render every `.md` under the output dir into `site/…html` (base-aware shell, `.md`→`.html` link rewrite), copy assets, **bundle the entry points**, **inline the data**, write `symbols.json`/`graph.json`, `graph.html`, `404.html` |
| `kodama_docs/js_bundle.py` | **new** — `bundle(webdir, entry)`: inlines the entry's ES-module graph onto a `__kodama_define`/`__kodama_require` registry → one classic script. Cycle/missing-file/unsupported-syntax all fail loud |
| `main.py` | `--static` flag → `render_all` then `static_site.build(cfg)` |
| `web/templates/page.html`, `graph.html` | `/…` → `{base}…`; `__KODAMA_SYMBOLS__`/`__KODAMA_GRAPH__` inline-data slots + a classic-script tag slot. Server passes `undefined` for the data and `type="module"` tags (behaviour unchanged) |
| `web/server.py` | pass `base='/'`, `symbols_json='undefined'`, `graph_json='undefined'`, module script tags into the template `.format()` calls (no behaviour change) |
| `web/sidebar.js` | `__KODAMA_BASE__` mode: inline-first data (fetch fallback), row hrefs, current-page detection |
| `web/app.js` | `__KODAMA_BASE__` mode: theme via `localStorage` |
| `web/graph.js` | `__KODAMA_BASE__` mode: inline-first data (fetch fallback) |
| `web/graph/panel.js` | `__KODAMA_BASE__` mode: page URL + body extraction from full page |
| `tests/test_static_site.py` | **new** — fixture output dir → built site assertions (layout incl. bundle presence / `fuzzy.js`+`graph/` absence, bases, rewrites, inline JSON == shipped JSON, no `type="module"`, no stray absolute paths) |
| `tests/test_js_bundle.py` | **new** — bundler subset parse/reject, cycle + missing + bare-specifier errors, and **node-executes both real bundles in a file:// harness** (inline data, DOM stub, `fetch` throws) |
| `tests/test_static_sidebar.js` | **new** — node guard test: static-mode hrefs/data URL with a `__KODAMA_BASE__` set before import |
| `manual_doc/…` | CLI page (`--static`), Rendering page, Output-formats table, Web-server page note |

## 4. Build algorithm (`static_site.build`)

1. Resolve roots: `out = cfg['output_dir']`, `site = <out>/site`,
   `webdir = <repo>/web`. Start from a clean `site/` (delete + recreate —
   same freshness policy as the manual copy).
2. **Assets**: copy `app.js`, `web/lib/` → `lib/`, `web/themes/` → `theme/`,
   and the repo-root `icon/` → `icon/`; then **bundle** `web/sidebar.js` and
   `web/graph.js` (all their imports inlined) to `site/sidebar.js` and
   `site/graph.js`. `fuzzy.js` / `web/graph/` are *not* copied — they ship
   inside the bundles.
3. **Data**: read `out/meta/symbols.json` (+ `out/meta/manual.json` when
   present) → slim index (same shape as `_symbols_index`) →
   `site/symbols.json`, keeping an escaped compact copy for inlining
   (`window.__KODAMA_SYMBOLS__`); copy `out/meta/graph.json` →
   `site/graph.json`, keeping an inline copy
   (`window.__KODAMA_GRAPH__` for `graph.html`).
4. **Pages**: for each `.md` under `out` that lives in `files/`, `manual/`,
   or is `index.md`: body = `render_md(md)` (the same renderer the server
   uses, so static pages look exactly like served ones) → internal
   `\.md"` hrefs → `\.html"` → wrap in the base-aware shell with
   `base = '../' × depth`, `theme` from `web/web_settings.yaml`
   (falling back to `web/theme_state.json`, then `light`), and the
   **inlined symbols JSON** in the `window.__KODAMA_SYMBOLS__` slot →
   `site/<same path>.html`. Non-`.md` files under `manual/` are copied
   verbatim (images etc. keep working via their relative links).
5. **graph.html** from `graph.html` template (depth 0, with the
   **inlined graph JSON** in `window.__KODAMA_GRAPH__`), plus a small
   `404.html` (GitHub Pages uses it) that offers a link back to `index.html`.
6. Log the result: page count + where the site is + a one-line GitHub Pages
   hint ("point a Pages repo at `site/`").

## 5. GitHub Pages deployment (what the user gets)

Option A — **Actions (recommended)**: push the repo, add the existing
`test.yml`-style workflow that runs the pipeline and uploads `site/` as the
Pages artifact. Zero manual steps per release.

Option B — **publish folder**: run `python main.py --config my.yaml --static`
locally, then either push the `site/` contents to a `gh-pages` branch or to
the repo's Pages folder setting; Pages serves `site/index.html` as the site
root.

Both work because the site is fully relative and has no server dependency.

## 6. Guarantees & limits

- Served mode (`--serve`) is **unchanged in behaviour** — the templates
  render with `base='/'`, JS without `__KODAMA_BASE__` takes the existing
  endpoint paths. Existing tests must keep passing unmodified.
- Static site over http(s) (GitHub Pages, `python -m http.server`): full
  feature parity — sidebar, search, graph, theme switching (per-browser).
- Static site over `file://`: **full feature parity** — content, code
  highlighting, theme, sidebar, search, and graph all work. Browsers block
  external ES modules and `fetch()` on `file://`, so the static build sidesteps
  both: the entry points ship as classic bundles and the data is inlined into
  the pages (§2). The only remaining `fetch` is the documented fallback for a
  server/host context.
- Theme choice in static mode is per-browser (`localStorage`), since there
  is no server to share a single choice with all visitors — the documented
  trade-off for a static deployment.
- `symbols.json` is generated, not handwritten; it always matches the last
  pipeline run (same as `meta/symbols.json` today).

## 7. Test plan

- `tests/test_static_site.py` (python): fixture docs dir (files + manual
  with an image + meta JSONs) → `build()` → assert layout (bundles present,
  `fuzzy.js` + `graph/` **absent**), per-depth bases, `.md`→`.html` rewrite
  (internal only, external kept), JSON payload shape, **inline data present
  and equal to the shipped JSON**, **no `type="module"`**, asset copy,
  injected `__KODAMA_BASE__`, no `src="/`/`href="/` leftovers,
  clean-rebuild freshness (a deleted page disappears on rebuild).
- `tests/test_js_bundle.py` (python + node): the supported import/export
  subset parses (aliases, multi-line braces, inline comments); default
  imports, re-exports, `import()`/`import.meta`, `export default`, cycles,
  missing modules and bare specifiers are all rejected loudly; and both real
  bundles (`sidebar.js`, `graph.js`) pass `node --check` and **execute in a
  file:// harness** — DOM stubbed, `fetch` throws, data supplied inline —
  asserting the sidebar tree renders and the search input is wired, and the
  graph evaluates cleanly.
- `tests/test_static_sidebar.js` (node, DOM stubs like the existing
  `test_sidebar_manual.js`): set `window.__KODAMA_BASE__` before import →
  assert file/fn/var/manual hrefs are base-relative `.html`, index href,
  and that the symbols fetch URL is `<base>symbols.json`.
- Existing suites stay green in server mode: `test_manual.py`,
  `test_web_manual.py`, `test_sidebar_manual.js`, `test_render_list.py`.
- End-to-end sanity: build `doc_self/site`, serve it read-only with
  `python -m http.server`, curl the index + one deep manual page + an asset
  to confirm every referenced path resolves.

## 8. Milestones (commits)

1. Plan doc (`STATIC_SITE.md`).
2. Base-aware templates + JS static mode (server mode proven unchanged by
   existing tests).
3. `static_site.py` + `main.py --static` + guard tests.
4. Manual updates + `doc_self/site` end-to-end verification.
5. `file://` support — `js_bundle.py` (classic bundles) + inline data
   (`window.__KODAMA_SYMBOLS__` / `window.__KODAMA_GRAPH__`) + bundler tests
   that execute the real bundles under a file:// harness.
