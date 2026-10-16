# Serving

kodama-docs ships a small, dependency-free web server (stdlib `http.server`). It serves the rendered `doc/` folder and adds a sidebar, search, theme switching, and a call-graph view. It binds to loopback by default, so it is safe to run on a workstation.

## Start it

```bash
python main.py --config settings.yaml --serve
```

`--serve` needs a previous run (it reads the rendered `doc/` and `meta/` folders). The bind address, port, theme, and docs folder come from `web_settings.yaml` (below) or the server defaults.

## web_settings.yaml

- `host` — bind address (default `127.0.0.1`).
- `port` — HTTP port.
- `default_theme` — `light` or `dark`.
- `docs_dir` — the folder to serve (defaults to `output_dir`).

## What it serves

- `/` — the app shell (sidebar + content pane).
- `/index.md`, `/files/...md` — rendered documentation pages.
- `/manual/...` — this manual (section 0); non-markdown files under it are served as raw assets.
- `/graph` — the interactive call-graph view.
- `/api/symbols` — the symbol index (drives search and the sidebar).
- `/api/graph` — the graph JSON used by the graph view.
- `/theme/<light|dark>/style.css`, `/app.js`, `/sidebar.js`, `/fuzzy.js`, `/graph.js` — the front-end assets.

## No server needed: `--static`

If you'd rather not run anything, build a static site:

```bash
python main.py --config settings.yaml --static
```

The run happens as usual, and afterwards `<output_dir>/site/` is written: the same documentation as plain `.html` files with relative paths, all assets copied in, and a `404.html`. `site/index.html` opens straight from disk, or point a GitHub Pages repo at `site/` and push — no server, no endpoints. Details in [Web Server](../03%20-%20Components/05%20-%20Web%20Server.md) and `STATIC_SITE.md`.

The full route list and how the front-end assembles a page is in [Web Server](../03%20-%20Components/05%20-%20Web%20Server.md).
