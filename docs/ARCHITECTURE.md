# T2URL — architecture

Natural-language text in, a governed table of URLs out. One capability, wired across
all five layers of the reference stack.

## The stack

```
                 ┌─────────────────────────────────────────────┐
   user  ──────► │  SERVE      app/                            │
   "cloudera     │             FastAPI + Jinja2, no JavaScript │
    cdp use      └────────────────┬────────────────────────────┘
    cases"                        │
                 ┌────────────────▼────────────────────────────┐
                 │  AI         ai/t2url.py                     │ ──► DuckDuckGo
                 │             text_to_urls()  via ddgs        │     Yahoo
                 └────────────────┬────────────────────────────┘     Startpage
                                  │ URLs, deduped, rank order        Yandex
                 ┌────────────────▼────────────────────────────┐
                 │  INGEST     data/db.py        (SQLite, dev) │
                 │             data/ingest/      (→ Iceberg)   │
                 └────────────────┬────────────────────────────┘
                 ┌────────────────▼────────────────────────────┐
                 │  LAKEHOUSE  t2url.raw_searches              │
                 │             t2url.raw_search_urls           │
                 └────────────────┬────────────────────────────┘
                 ┌────────────────▼────────────────────────────┐
                 │  PROCESS    pipelines/jobs/url_enrichment   │
                 │             normalise · dedupe · enrich     │
                 └────────────────┬────────────────────────────┘
                                  ▼
                          t2url.curated_urls

         ══════════ governed end to end by SDX ══════════
         Ranger policies · Atlas lineage · model card
```

## Layer by layer

| Layer | Directory | Component | Cloudera service |
|---|---|---|---|
| **Serve** | `app/` | FastAPI + Jinja2 dashboard | Cloudera AI Application |
| **AI** | `ai/` | `text_to_urls()` — metasearch retrieval | Cloudera AI Workbench |
| **Ingest** | `data/ingest/` | SQLite → Iceberg batch loader | Cloudera Data Engineering |
| **Lakehouse** | `data/iceberg/` | `raw_searches`, `raw_search_urls`, `curated_urls` | Iceberg on CDW / Data Lake |
| **Process** | `pipelines/` | URL normalisation and enrichment | Cloudera Data Engineering |
| **Governance** | `governance/` | Ranger policies, model card, classification | SDX |

## The request path

A search is synchronous and touches three layers:

1. **`POST /search`** — `app/server.py` whitelists every option against `OPTIONS`,
   clamps `max_results` to 1–50, and joins the checked engines into a fallback chain.
2. **Retrieval** — `t2url.text_to_urls()` calls `ddgs`, which queries engines in
   order until it has enough results. Returns URLs deduplicated, in rank order.
3. **Persist** — `db.save_search()` writes the query, its full option set, and the
   URLs in one transaction.
4. **303 redirect** back to `/` with a flash message. Reloading never re-runs a
   search.

The batch path runs on a schedule and never blocks a user: ingest at 02:00, enrichment
at 02:30, both idempotent.

## Decisions worth defending

**SQLite is not a placeholder — it is the demo path.** An accelerator has to run on
a laptop during Discover, before any CDP environment exists. The two tiers share a
schema shape, and `data/ingest/load_to_iceberg.py` is the bridge. What would be
wrong is *pretending* SQLite is the production store; the split is explicit.

**No JavaScript in the Serve layer.** The whole accelerator installs with
`make install` and runs with one command. That keeps the
Discover → Qualify demo loop short, which is worth more here than a richer UI. The
cost is real — no incremental updates, a full page render per action — and the
swap path is documented in [`app/README.md`](../app/README.md).

**Multi-engine is resilience, not a merge.** `ddgs` tries engines in order and stops
once it has `max_results`. A throttled engine falls through instead of failing the
search. Order is load-bearing; measure it with `ai/notebooks/retrieval_eval.ipynb`
before changing it.

**The Process layer normalises; the local dedupe does not.** `db.dedupe_urls()`
compares raw strings. The Spark job strips `www.`, tracking parameters, and
fragments first, then aggregates rather than deletes — duplicates are signal
(`times_seen`), not noise. The divergence is deliberate: the job is strictly more
aggressive, never less, and
[`tests/data_quality/`](../tests/data_quality/test_url_normalization.py) asserts it.

**Links only, never page content.** Enforced structurally: there is no HTTP client
anywhere in this repo that fetches a result page. `ai/t2url.py` reads `href` and
discards the rest. Adding a fetcher is a classification change, not a feature.

## Where the layering is tested

The Serve layer holds no SQL and no retrieval logic; `data/db.py` holds every
statement; `ai/t2url.py` has no database and no HTTP handling. The check on that
claim is concrete: swapping the front-end for React should require no change in
`ai/`, `data/`, `pipelines/`, or `governance/`.

## Known constraints

- **Query text leaves the environment.** Searches go to third-party public endpoints
  with no API key and therefore no data-processing agreement. This is a deployability
  constraint, not a footnote — raise it first with any customer whose data cannot
  leave. See
  [`governance/DATA_CLASSIFICATION.md`](../governance/DATA_CLASSIFICATION.md#third-party-disclosure).
- **Retrieval is not reproducible.** Engines re-rank continuously; the same query
  tomorrow returns different URLs. Every search persists its full option set and
  timestamp, so a result set is *explainable* even when it is not repeatable.
- **Absence is not evidence.** Results are what a public engine ranked in the top N.
  A missing URL does not mean the page does not exist. Never use T2URL output to
  conclude a document does not exist.
- **SQLite serialises writes.** Fine for a demo, wrong for concurrent users. The
  Iceberg tier is the answer, and the ingest bridge is where that transition happens.

## Scale

T2URL's volume is small — a search is a form post, not a stream. The sizing across
`infra/` and `pipelines/cde/` reflects that deliberately: CDE scales to zero between
runs, executors are modest, enrichment is daily. **Raise these from measured spill,
not from optimism.** The architecture that would change first if volume grew is
ingest — DataFlow earns its place when searches arrive from a live feed rather than
a form.
