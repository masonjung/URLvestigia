# `app/` — Serve layer

The reference front-end. This is what a stakeholder actually opens, and the only
layer with a UI.

T2URL's Serve layer is **FastAPI + Jinja2, rendered entirely server-side with no
JavaScript and no build step**. That is a deliberate choice, not a gap: the whole
accelerator installs with `make install` and runs with one command, which keeps the
Discover → Qualify demo loop short.

## What's here

| Path | What it is |
|---|---|
| `server.py` | The FastAPI app: renders the page, handles form posts, validates every option against a whitelist |
| `templates/index.html` | The entire UI — one Jinja2 template, HTML + CSS only |
| `requirements.txt` | This layer's dependencies, pulling in `ai/` since `server.py` imports it |
| `__init__.py` | Makes `app` importable so `uvicorn app.server:app` resolves |

Dependencies live with their layer, the same way the Forge template keeps
`package.json` inside `app/`. Because the Serve layer pulls in the AI layer,
`app/requirements.txt` plus `tests/requirements.txt` is the full closure — that is
what `make install` installs.

## Run it

```bash
make dev                                  # → http://127.0.0.1:8000/
uvicorn app.server:app --reload           # same thing, without make
```

## How it wires to the other layers

`server.py` puts `ai/` and `data/` on the import path, then calls into them:

```
app/server.py
  ├── import t2url   → ai/t2url.py     (AI layer: text → ranked URLs)
  └── import db      → data/db.py      (Lakehouse layer: persist searches + URLs)
```

The Serve layer holds **no business logic and no SQL**. Retrieval belongs to
`ai/`, persistence belongs to `data/`. If you find yourself writing a query here,
it belongs in `data/db.py`.

## Conventions

- **POST-redirect-GET everywhere.** Every mutation (`/search`, `/delete/{id}`,
  `/dedupe`, `/clear`) ends in a 303 back to `/` carrying a `?msg=` flash. Reloading
  never re-runs a search.
- **Whitelist every input.** `OPTIONS` in `server.py` is the single source of truth
  for allowed `timelimit` / `backend` / `safesearch` / `region` values; `_pick()`
  falls back to the first entry. `max_results` is clamped to 1–50. Nothing
  user-supplied reaches the search engines unchecked.
- **One template.** Styles live in the `<style>` block in `index.html`. The design
  tokens are the `:root` custom properties — see
  [`docs/architecture/DESIGN_TEMPLATE.md`](../docs/architecture/DESIGN_TEMPLATE.md).

## Which Cloudera tool automates it

Deployed as a **Cloudera AI Application** (formerly CML Applications) — a
long-running hosted web service inside the AI Workbench, fronted by Knox and
authenticated through SDX. `infra/cdp/provision.sh` creates the workspace;
`.cicd/deploy.sh` registers and restarts the application.

Because it is a plain ASGI app, it also runs unchanged in any container runtime —
useful for local demos before a CDP environment exists.

## If you swap in a JavaScript front-end

The Forge template's reference app is React 19 + TypeScript + Tailwind + Vite. If
this accelerator moves that way, keep `server.py` as the JSON API, add the SPA
under `app/web/`, and point `make dev` at both. Nothing in `ai/`, `data/`,
`pipelines/`, or `governance/` should need to change — that is the test of whether
the layering held.
