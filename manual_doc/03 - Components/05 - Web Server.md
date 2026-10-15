# Web server

`main.py --serve` (implemented in `web/server.py`, a stdlib `ThreadingHTTPServer`) serves the rendered documentation set over HTTP. It is a *presentation layer only*: it reads the output of a previous run and never generates anything.

## What it serves

| Route | What |
| --- | --- |
| `/` | redirect to `/index.md`. |
| `/<path>.md` | a documentation page, rendered to HTML (markdown subset + code highlighting via highlight.js; raw `<a id>` anchors are preserved, so `#fn-…` links from the generated pages work). |
| `/page/<path>.md` | the same page's body **without** the page shell — used by the graph view to jump into a page. |
| `/graph` | the interactive call-graph page (d3-free custom canvas/JS in `web/graph/`), fed by `/api/graph`. |
| `/api/graph` | `meta/graph.json` (so the graph view needs `project.copy_meta` or a previous run with it). |
| `/api/symbols` | a compact symbol index for the graph search box. |
| `/manual/<asset>` | non-markdown files that shipped with a configured `project.manual_doc` folder (images, css, …) — served raw, never rendered. |
| `/theme/{light,dark}/style.css` | the two themes. |
| `/lib/…`, `/app.js`, `/graph.js`, `/sidebar.js`, `/fuzzy.js` | the server's own static assets (highlight.js included, no CDN — the server works fully offline). |

## Settings — `web/web_settings.yaml`

| Key | Default | Meaning |
| --- | --- | --- |
| `host` | `127.0.0.1` | bind address (set `0.0.0.0` to reach it from other machines). |
| `port` | `8123` | listen port. |
| `default_theme` | `light` | initial theme; the page button switches at runtime. |
| `docs_dir` | (empty) | serve *this* docs directory instead of the main config's `project.output_dir` — handy for previewing a different build without re-running. |

## Theme switching

The theme button posts to `POST /api/theme` (`light` or `dark`); the choice is persisted in `web/theme_state.json` next to the server code, which overrides `default_theme` until changed again, and applies to every connection.

## Notes

- The server needs a previous documentation run (it reads `<output_dir>/index.md`, `files/`, and `meta/graph.json`); there is no in-memory generation.
- `--serve` is a separate mode from the pipeline: the backend-management flags (`--list-backends` / `--install` / `--remove`) run first and exit, so they never combine with `--serve` in one invocation.
- Paths are served strictly inside the docs root (a `..` escape returns 404), so it is safe to expose on a LAN.

Related: [Serving](../01%20-%20Getting%20Started/04%20-%20Serving.md), [Rendering](../02%20-%20How%20It%20Works/07%20-%20Rendering.md), [CLI](06%20-%20CLI.md).
