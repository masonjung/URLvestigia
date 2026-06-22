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

The UI ships with a precompiled `web/main.js`, so no Node toolchain is needed to
run it. If you edit `web/main.ts` and want to recompile (requires Node):

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
