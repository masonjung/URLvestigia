# T2URL — Cloudera Forge Accelerator

**Natural-language text in, a governed table of URLs out.** Type a question, get a
persisted list of source links — with the query, provider, engines, region, and time
window stored alongside, so a search becomes an artifact instead of an activity.

Search the web, Wikipedia, OpenAlex, or arXiv. Each exposes only the options it
genuinely applies, and the record says which.

Built to the Cloudera Forge standard accelerator layout: every layer of the reference
stack — Ingest → Lakehouse → Process → AI → Serve — wired end to end and governed by
SDX.

Free to run: no API keys, no accounts, no build step. The only external services it
talks to are public search-engine pages and three keyless non-profit APIs.

**New here?** Walk [`docs/EXAMPLE.md`](docs/EXAMPLE.md) — one search traced across all
five layers in about 20 minutes, on a laptop. Then use
[`docs/GATES.md`](docs/GATES.md) to know what "done" means at each phase.

## Quickstart

```bash
# 1. Run the reference app (the Serve layer)
make install
make dev                 # → http://127.0.0.1:8000/

# 2. The Harden gate
make test                # 186 passing, 13 skipped (the live tier)

# 3. See how the whole solution deploys (every step dry-runs)
make -n deploy
make help                # list all targets

# 4. Start a new accelerator from this template
make new VERTICAL=healthcare USECASE=readmission-risk
```

Nothing in this repo changes a remote system without an explicit `--execute`.

## The standard repo

```
T2URL/
├── docs/         architecture · business case          → operating model + design system
├── infra/        IaC — CDP CLI / Terraform             → one-time platform provisioning
├── data/         SQLite dev store · Iceberg DDL        → Ingest + Lakehouse layers
├── pipelines/    Data Engineering (Spark) jobs         → Process layer
├── ai/           retrieval · notebooks · eval          → AI layer
├── app/          FastAPI + Jinja2 dashboard            → Serve layer
├── governance/   SDX policies · model card            → security · policy · lineage
├── tests/        data quality · AI eval harness        → the Harden gate
├── .cicd/        build → test → deploy                 → one Git-driven pipeline
├── .gitlab/      MR + issue templates                  → the process, where the work is
├── scripts/      new-accelerator.sh                    → scaffold the next one
└── Makefile      make deploy                           → one command to ship
```

Each directory has a `README.md` explaining what goes there, the naming conventions,
and which Cloudera API/tool automates it.

## How a search flows

```
"cloudera cdp use cases"
        │
        ▼
   app/server.py ──── whitelists every option, clamps max_results to 1–50
        │
        ▼
   ai/t2url.py ────── one provider per search:
        │             ddgs → DuckDuckGo · Yahoo · Startpage · Yandex
        │                    fallback chain: a throttled engine doesn't fail it
        │             wikipedia · openalex · arxiv → their own keyless APIs
        │             options a provider can't apply are dropped, then stored NULL
        ▼
   data/db.py ─────── SQLite (dev)  ──► data/ingest/ ──► Iceberg raw tables
        │                                                      │
        ▼                                                      ▼
   303 redirect, results rendered              pipelines/jobs/url_enrichment.py
                                                normalise · dedupe · enrich
                                                        │
                                                        ▼
                                                t2url.curated_urls
```

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## The four standard components

| Component | What it is | Read |
|---|---|---|
| A way to choose | Weighted scoring; ≥ 4.0 / 5 advances | [`.gitlab/issue_templates/`](.gitlab/issue_templates/Use-Case-Candidate.md) · [`BUSINESS_CASE.md`](docs/BUSINESS_CASE.md) |
| A build process | 6-phase stage gate, one accountable owner per phase | [`docs/GATES.md`](docs/GATES.md) |
| A build standard | Ingest → Lakehouse → Process → AI → Serve, governed by SDX | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| A standard deliverable | This repo — deploys clean from the repo alone | [`.cicd/`](.cicd/README.md) |

## What's in here

- **`app/`** — a complete, working config-free dashboard: FastAPI + Jinja2, rendered
  entirely server-side with **no JavaScript and no build step**. Every option is
  whitelist-validated; every mutation is POST-redirect-GET. The design system is
  documented in [`docs/architecture/DESIGN_TEMPLATE.md`](docs/architecture/DESIGN_TEMPLATE.md).
- **`ai/`** — `text_to_urls()`, the whole capability behind one function, with four
  selectable corpora and a support matrix that decides what each one may be asked;
  plus an eval notebook that measures availability and overlap before you change a
  default.
- **`data/` `pipelines/` `governance/` `infra/` `tests/`** — a thin but complete
  accelerator wired across every layer: Iceberg DDL, a Spark enrichment job with a CDE
  job spec, Ranger policies with a masking rule, CDP CLI *and* Terraform provisioning,
  and 186 passing tests. Walkthrough: [`docs/EXAMPLE.md`](docs/EXAMPLE.md).
- **`scripts/new-accelerator.sh`** (via `make new`) — clones this template into a
  fresh, re-pointed, git-initialised accelerator repo.

## Use the library directly

```python
from t2url import text_to_urls

urls = text_to_urls("best python web scraping libraries", max_results=10)
```

Options: `provider` (`"ddgs"`, `"wikipedia"`, `"openalex"`, `"arxiv"`), `max_results`
(10), `region` (`"wt-wt"`, e.g. `"us-en"`, `"kr-kr"`), `safesearch` (`"on"` /
`"moderate"` / `"off"`), `timelimit` (`None`, `"d"`, `"w"`, `"m"`, `"y"`), and
`backend` — one engine or a comma-delimited fallback chain (`"duckduckgo,yahoo"`).
URLs come back deduplicated, in ranking order.

**Not every provider supports every option**, and the ones that don't apply are
dropped rather than silently ignored — `region` selects a Wikipedia language
edition, `timelimit` filters OpenAlex and arXiv by publication date, and neither
`safesearch` nor the engine chain means anything outside `ddgs`. The support matrix
and the reasoning are in [`ai/README.md`](ai/README.md).

## The ~8-week lifecycle

| Week | wk 0 | wk 1 | wk 2 | wk 3–6 | wk 7 | wk 8 |
|---|---|---|---|---|---|---|
| **Phase** | Discover | Qualify | Architect | Build | Harden | Publish → Deployed |

From selected use case to a deployed, governed solution. The Build phase scales with
complexity.

## Status — read before deploying

T2URL is **⚠️ incomplete at the Harden gate**, stated here rather than discovered in
a review:

- The retrieval model card has **no dated evaluation run** — run
  `ai/notebooks/retrieval_eval.ipynb`.
- `raw_searches` has **no row-level retention policy**. Iceberg snapshot expiry
  governs time travel, not rows.
- `ingress_cidrs` still defaults to `0.0.0.0/0` — fine for a sandbox, wrong anywhere
  else.

And one constraint that is a property of the design, not a gap: **query text leaves
the customer's environment.** Searches go to third-party public endpoints with no API
key and therefore no data-processing agreement. Raise this first with any customer
whose data cannot leave. See
[`governance/DATA_CLASSIFICATION.md`](governance/DATA_CLASSIFICATION.md).

## Storage

Two tiers, one schema shape. **SQLite** for local development — a single file at
`data/t2url.db`, moved with the `T2URL_DB` environment variable — and **Apache
Iceberg** for the platform. SQLite is not a placeholder: an accelerator has to run on
a laptop before any CDP environment exists.
[`data/ingest/load_to_iceberg.py`](data/ingest/load_to_iceberg.py) is the bridge.

Only links are stored, never page content.
