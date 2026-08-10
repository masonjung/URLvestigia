# `ai/` — AI layer

Text in, ranked URLs out. This is the layer that does the actual discovery work;
everything else stores, processes, or displays what this layer returns.

## What's here

| Path | What it is |
|---|---|
| `t2url.py` | The retrieval façade — dispatch, dedupe, and the `ddgs` path |
| `providers.py` | The support matrix, the one HTTP seam, and the Wikipedia / OpenAlex / arXiv providers |
| `notebooks/retrieval_eval.ipynb` | Coverage / overlap evaluation, run before changing defaults |
| `requirements.txt` | One dependency: `ddgs`. No web framework, no database driver, no HTTP library. |

## The capability

```python
from t2url import text_to_urls

urls = text_to_urls(
    "best python web scraping libraries",
    provider="ddgs",         # "ddgs" | "wikipedia" | "openalex" | "arxiv"
    max_results=10,
    region="wt-wt",          # locale: "us-en", "kr-kr", … or "wt-wt" worldwide
    safesearch="moderate",   # "off" | "moderate" | "on"
    timelimit=None,          # None | "d" | "w" | "m" | "y"
    backend="duckduckgo",    # one engine, or a comma-delimited fallback chain
)
```

Returns URLs **deduplicated, in ranking order**. Never page content — see
[`governance/DATA_CLASSIFICATION.md`](../governance/DATA_CLASSIFICATION.md).

## Providers and what each one supports

One search uses one provider. Options a provider does not apply are **dropped before
the call**, not passed and ignored — so a caller can never believe a filter ran when
it did not.

| Provider | Corpus | `region` | `timelimit` | `safesearch` | `backend` |
|---|---|---|---|---|---|
| `ddgs` | Web, via DuckDuckGo / Yahoo / Startpage / Yandex | locale bias | ✓ | ✓ | engine chain |
| `wikipedia` | Encyclopedia, via the MediaWiki API | language edition | — | — | — |
| `openalex` | ~250M scholarly works | — | publication date | — | — |
| `arxiv` | Preprints (physics, maths, CS, …) | — | submission date | — | — |

`max_results` is absent from the table because every provider honours it.

The matrix lives in `providers.SUPPORTS` and is declared **once**. It decides which
kwargs reach a provider, which columns `app/server.py` writes versus leaves `NULL`,
which controls the template renders, and the CSS that hides the rest. Copy it
somewhere and the copies will drift; the symptom is a UI knob that silently does
nothing.

Two deliberate omissions:

- **`region` is not offered for OpenAlex.** It has a country filter, but on author
  affiliation rather than the locale of the work. Under a control that means "result
  locale" elsewhere, that would misreport what was applied.
- **`safesearch` exists only for `ddgs`.** The other three curate their own corpora
  and expose no equivalent, so claiming one would be fiction.

### Why not just use the `ddgs` wikipedia backend?

ddgs can reach Wikipedia, but it cannot map a region onto the language edition — and
that mapping is the only thing that makes `region` meaningful for an encyclopedia.
`ko.wikipedia.org` is a different corpus, not a Korean ranking of the English one.
The direct API also does not depend on scraping tolerance.

### `T2URL_CONTACT`

Wikipedia, OpenAlex, and arXiv ask callers to identify themselves — Wikipedia via a
descriptive `User-Agent`, OpenAlex via a `mailto` that admits you to its faster
polite pool. Set `T2URL_CONTACT` to a **team or service address**:

```bash
export T2URL_CONTACT="data-platform@example.com"
```

Not a key, not billed, and not required — unset degrades to the anonymous rate-limit
pool rather than failing, so a fresh clone runs with nothing configured. Set it
before running anything at volume, or throttling will look like a broken provider.
It is an outbound identifier, so it is a disclosure consideration: see
[`governance/DATA_CLASSIFICATION.md`](../governance/DATA_CLASSIFICATION.md#the-t2url_contact-identifier).

## Retrieval hyperparameters

These are the knobs the Serve layer exposes and the eval harness sweeps. Defaults
are what `text_to_urls` uses when the caller says nothing.

| Parameter | Default | Range | Effect |
|---|---|---|---|
| `provider` | `"ddgs"` | `ddgs`, `wikipedia`, `openalex`, `arxiv` | Which corpus to search. Not a fallback chain — see below. |
| `max_results` | `10` | 1–50 (clamped in `app/server.py`) | Result ceiling. Re-applied centrally, so it holds however a provider behaves. |
| `region` | `"wt-wt"` | `wt-wt`, `us-en`, `uk-en`, `kr-kr`, `jp-jp`, `de-de`, `fr-fr` | Locale bias for `ddgs`; language edition for `wikipedia`. Ignored elsewhere. |
| `safesearch` | `"moderate"` | `off`, `moderate`, `on` | Engine-side content filter. `ddgs` only. |
| `timelimit` | `None` | `None`, `d`, `w`, `m`, `y` | Recency window. `None` = any time. Ignored by `wikipedia`. |
| `backend` | `"duckduckgo"` | comma-delimited chain | Engine fallback order. `ddgs` only. |

## Two kinds of "more than one source"

**Within `ddgs`, `backend` is a fallback chain.** It accepts a comma-delimited list —
`"duckduckgo,yahoo,startpage,yandex"`. This is **resilience, not a merge**: ddgs tries
engines in order and stops as soon as it has `max_results`, so one throttled engine
does not fail the search. Order matters; the first engine supplies most results in
the common case.

Only four engines are exposed in the UI. ddgs also supports google, brave, and
mojeek, but they are blocked or return empty too often to be a dependable default.
Re-check with `notebooks/retrieval_eval.ipynb` before promoting one.

**Across providers there is no chain, and that is deliberate.** Fall-through assumes
the sources are substitutes. These are different corpora, so falling through from a
web engine to arXiv would answer a product question with physics preprints and look
like a successful search. The near-zero overlap that makes them worth having is
exactly what makes them bad fallbacks. Merging results across providers is a separate
feature with its own prerequisites — see the ADR note in
[`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

The practical reason the three API providers exist: every `ddgs` engine is reached by
one mechanism, so rate limiting, IP blocking, and markup changes hit all four at
once. A datacenter egress IP is the profile those engines block hardest, so a search
that works on a laptop can return `[]` from a CML session. The API providers do not
share that failure mode.

## Adding a provider

If the seam is right this is small. It should be:

1. A function in `providers.py` taking `(text, *, max_results, **options)` and
   returning absolute `http(s)` URLs in rank order.
2. One entry in `REGISTRY` and one in `SUPPORTS`.
3. One entry in `OPTIONS["provider"]` and `PROVIDER_LABELS` in `app/server.py`.
4. Tests in `tests/test_providers.py`.

No changes to the template, the schema, or the contract tests. If a provider *does*
require them, the abstraction is wrong — which is worth knowing, since demonstrating
clean extension is a large part of what this accelerator is for.

Use the single `_get_bytes` seam rather than calling `urllib` directly, or the
suite's network guard will not cover the new provider and CI will quietly start
making real requests.

## Conventions

- **This layer does search and nothing else.** No persistence, no request handling.
  It is importable and testable with no database and no server running, and its only
  dependency is `ddgs` — the API providers use stdlib `urllib` and `xml.etree` to
  keep that true.
- **One HTTP seam.** Every outbound request goes through `providers._get_bytes`.
  That is what the test suite severs to guarantee no network in the default run, and
  where any retry or proxy policy belongs. Do not call `urllib` directly.
- **Normalize at the boundary.** ddgs renamed its result key from `url` to `href`;
  `text_to_urls` accepts either so a library upgrade cannot silently return zero
  results. OpenAlex gets the same treatment — `doi` → `landing_page_url` → `id`.
  Keep that defensiveness when adding fields.
- **Deduplicate on the way out**, preserving rank order. Downstream layers assume
  the list is already clean.
- **Never let an unsupported option through.** Dropping it is not a courtesy, it is
  what keeps the persisted record true. A provider that silently ignores a filter
  produces a search that cannot be reproduced from what was stored about it.
- **Assert on the request, not just the response.** arXiv accepted a date filter,
  ignored it for multi-word queries, and returned a normal-looking result set — a
  test checking only the returned URLs would have passed. `tests/test_providers.py`
  inspects the outbound call for this reason.

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
