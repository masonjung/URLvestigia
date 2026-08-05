# `ai/` — AI layer

Text in, ranked URLs out. This is the layer that does the actual discovery work;
everything else stores, processes, or displays what this layer returns.

## What's here

| Path | What it is |
|---|---|
| `t2url.py` | The retrieval module — the accelerator's core capability |
| `notebooks/retrieval_eval.ipynb` | Engine coverage / overlap evaluation, run before changing defaults |
| `requirements.txt` | One dependency: `ddgs`. No web framework, no database driver. |

## The capability

```python
from t2url import text_to_urls

urls = text_to_urls(
    "best python web scraping libraries",
    max_results=10,
    region="wt-wt",          # locale: "us-en", "kr-kr", … or "wt-wt" worldwide
    safesearch="moderate",   # "off" | "moderate" | "on"
    timelimit=None,          # None | "d" | "w" | "m" | "y"
    backend="duckduckgo",    # one engine, or a comma-delimited fallback chain
)
```

Returns URLs **deduplicated, in ranking order**. Never page content — see
[`governance/DATA_CLASSIFICATION.md`](../governance/DATA_CLASSIFICATION.md).

## Retrieval hyperparameters

These are the knobs the Serve layer exposes and the eval harness sweeps. Defaults
are what `text_to_urls` uses when the caller says nothing.

| Parameter | Default | Range | Effect |
|---|---|---|---|
| `max_results` | `10` | 1–50 (clamped in `app/server.py`) | Result ceiling. ddgs stops querying engines once it has this many. |
| `region` | `"wt-wt"` | `wt-wt`, `us-en`, `uk-en`, `kr-kr`, `jp-jp`, `de-de`, `fr-fr` | Locale bias. Materially changes ranking for non-English queries. |
| `safesearch` | `"moderate"` | `off`, `moderate`, `on` | Engine-side content filter. |
| `timelimit` | `None` | `None`, `d`, `w`, `m`, `y` | Recency window. `None` = any time. |
| `backend` | `"duckduckgo"` | comma-delimited chain | Engine fallback order. |

## The engine fallback chain

`backend` accepts a comma-delimited list — `"duckduckgo,yahoo,startpage,yandex"`.
This is **resilience, not a merge**: ddgs tries engines in order and stops as soon
as it has `max_results`, so one throttled engine does not fail the search. Order
matters; the first engine supplies most results in the common case.

Only four engines are exposed in the UI. ddgs also supports google, brave, mojeek,
and wikipedia, but they are blocked or return empty too often to be a dependable
default. Re-check with `notebooks/retrieval_eval.ipynb` before promoting one.

## Conventions

- **This module does search and nothing else.** No persistence, no HTTP handling.
  It is importable and testable with no database and no server running.
- **Normalize at the boundary.** ddgs renamed its result key from `url` to `href`;
  `text_to_urls` accepts either so a library upgrade cannot silently return zero
  results. Keep that defensiveness when adding fields.
- **Deduplicate on the way out**, preserving rank order. Downstream layers assume
  the list is already clean.

## Which Cloudera tool automates it

Runs in a **Cloudera AI (CML) Workbench session** for interactive work, and is
imported directly by the Serve layer in production. When retrieval grows past a
single function — query expansion, an LLM reranker, an agent loop — the natural
next step is a **Cloudera AI Model** endpoint (or NVIDIA NIM for a hosted LLM),
with this module becoming the client. Register the endpoint in
`governance/model_cards/` when that happens.

## Before you change a default

Run the eval notebook and record the result in the model card. Retrieval defaults
are the accelerator's most load-bearing configuration — a region or engine change
alters every downstream table.
