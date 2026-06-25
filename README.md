# T2URL

Turn natural-language text into a list of URLs using DuckDuckGo web search.

It works in two modes:

- **Plain search** (default) — your text is sent straight to DuckDuckGo.
- **LLM-augmented search** (optional) — Claude first expands your text into
  several focused search queries, each is searched, and the results are merged.

## Install

```bash
pip install -r requirements.txt
```

`ddgs` is required. `anthropic` is only needed if you use `augment=True`.

## Web UI

A plain HTML + TypeScript frontend talks to a FastAPI server that wraps the
library. Start the server and open the page:

```bash
uvicorn server:app --reload
# then open http://127.0.0.1:8000/
```

Type a request, optionally tick **Refine with AI** (needs `ANTHROPIC_API_KEY`),
and you get a clickable list of URLs.

The UI ships with a precompiled `02_web/main.js`, so no Node toolchain is needed
to run it. If you edit `02_web/main.ts` and want to recompile (requires Node):

```bash
npm install
npm run build    # or: npm run watch
```

### API

The server exposes one endpoint:

```
POST /api/search
{ "text": "...", "max_results": 10, "augment": false }
->
{ "query": "...", "urls": ["https://...", ...] }
```

### Hardening / deployment

Each search hits DuckDuckGo (and, with `augment`, an LLM), so the server applies
some basic abuse protection. All are configurable via environment variables:

| Variable              | Default                          | Purpose                                              |
|-----------------------|----------------------------------|------------------------------------------------------|
| `T2URL_RATE_LIMIT`    | `20/minute`                      | Per-IP rate limit on `POST /api/search`.             |
| `T2URL_ALLOW_ORIGINS` | localhost dev origins            | Comma-separated CORS allowlist (`*` to allow all).   |
| `T2URL_ADMIN_TOKEN`   | _unset_ (DELETE routes open)     | When set, `DELETE /api/searches*` require an `X-Admin-Token` header. |
| `T2URL_DB`            | `t2url.db` in the repo root      | Override the SQLite database path.                   |

For local single-user use the defaults are fine. If you expose the server,
set `T2URL_ALLOW_ORIGINS` to your real frontend origin and `T2URL_ADMIN_TOKEN`
to a secret so the history-clearing endpoints aren't open to everyone.

## Project layout

```
01_t2url/t2url/   the Python library (text -> URLs, search, augment, db)
02_web/           static HTML + TypeScript frontend
server.py         FastAPI app wiring the two together
```

`01_t2url` acts as a numbered "src" directory: `server.py` and `example.py` add
it to the import path so the package is still imported as `from t2url import ...`.

## Usage

```python
from t2url import text_to_urls

# Plain search — no API key needed
urls = text_to_urls("best python web scraping libraries", max_results=10)

# LLM-augmented search — needs ANTHROPIC_API_KEY in your environment
urls = text_to_urls(
    "how do I keep my houseplants alive in winter",
    max_results=10,
    augment=True,
)
```

### `text_to_urls(text, *, ...)`

| Argument      | Default            | Description                                              |
|---------------|--------------------|----------------------------------------------------------|
| `max_results` | `10`               | Max URLs returned overall.                               |
| `augment`     | `False`            | Use Claude to refine the query first.                    |
| `max_queries` | `3`                | When augmenting, max queries to generate.                |
| `region`      | `"wt-wt"`          | DuckDuckGo region code (e.g. `"us-en"`).                 |
| `safesearch`  | `"moderate"`       | `"on"`, `"moderate"`, or `"off"`.                        |
| `model`       | `"claude-opus-4-8"`| Anthropic model ID (augment only).                       |
| `client`      | `None`             | Reuse an `anthropic.Anthropic()` instance (augment only).|

You can also call the plain search directly:

```python
from t2url import search_urls
urls = search_urls("python json parsing", max_results=5)
```

## How augmentation works

With `augment=True`, your input is sent to Claude with a request to produce a
handful of focused, keyword-style search queries covering distinct angles of
the request. Each query is run through DuckDuckGo and the URLs are deduplicated
(original ranking order preserved) up to `max_results`. If the model returns
nothing usable, it falls back to searching your original text.
