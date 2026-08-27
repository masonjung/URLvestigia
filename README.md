<div align="center">
  <img width="550" height="300" alt="image" src="https://github.com/user-attachments/assets/180ab986-59f6-4e4c-ba93-e20df8e4ba56"/>
</div>


# URLvestigia

**Natural-language text in, a governed table of URLs out.**


<img width="1092" height="657" alt="image" src="https://github.com/user-attachments/assets/220a34d5-11fe-4830-bd64-7a5b6b3f987f" />



## Table of Contents

- [Overview](#overview)
- [Demo](#demo)
- [Use Case](#use-case)
- [Key Features](#key-features)
- [Quickstart](#quickstart)
- [Architecture / Software Components](#architecture--software-components)
- [Target Audience](#target-audience)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Hardware Requirements](#hardware-requirements)
- [Documentation](#documentation)
- [Status](#status)
- [Planned platform integration](#planned-platform-integration)

## Overview

URLvestigia turns a plain-English question into a persisted, queryable table of source
links — and records the query, provider, engines, region, safesearch setting, and time
window alongside every result, so a search becomes an artifact instead of an activity.
It searches the open web, Wikipedia, OpenAlex, or arXiv, with no API keys, no accounts,
and no build step. Built to the Cloudera Forge standard accelerator layout
(Ingest → Lakehouse → Process → AI → Serve), it is designed to land its output in a
governed Iceberg lakehouse under SDX, so the source list behind any downstream analysis
or RAG corpus can be audited and reproduced months later. **Retrieval, Serve, and local
storage are finished and run today; the CDP platform layers are written against the same
schema but not yet connected** — see [Planned platform integration](#planned-platform-integration).

## Demo

[Link to Reprise demo walking through the blueprint solution — TO BE ADDED]

In the meantime, [`docs/EXAMPLE.md`](docs/EXAMPLE.md) traces one search across all five
layers in about 20 minutes, on a laptop, with nothing provisioned.

## Use Case

Teams assembling a source corpus — for a research review, a competitive scan, a
regulatory filing, or a RAG pipeline — can usually show *what* they collected but not
*how*. The search that produced the list is a transient activity: run in a browser or a
notebook, with settings that are never written down and results that cannot be
reproduced once the engine's ranking drifts. When the corpus is later questioned, there
is no record of which engine was queried, in which region, over which time window, or
with what filtering applied.

URLvestigia closes that gap by treating the search configuration as part of the record.
Each run is written as a structured row capturing both the returned URLs and the full
option set that produced them. The business outcome is an auditable, reproducible corpus
assembly step upstream of whatever consumes it — governed by the same SDX policies as
the rest of the lakehouse, rather than living in a browser history.

## Key Features

- **Every search is recorded as a governed artifact**, not just its results — query,
  provider, engines, region, safesearch, and time window are stored with the URLs.
- **Four corpora behind one function call** — open web, Wikipedia, OpenAlex, arXiv —
  each exposing only the options it genuinely supports, with unsupported options dropped
  rather than silently ignored.
- **Runs on a laptop in one command**, with no API keys, no accounts, and no build step;
  the only external calls are to public search pages and three keyless non-profit APIs.
- **Designed for the governed lakehouse** — the Iceberg schema, DDL, loader, and
  enrichment job are written against the same shape the local store already uses.
- **Reusable as an accelerator template** — `make new` clones the tracked layout into a
  fresh repo, keeping every directory `README.md` and clearing the worked example.
- **Verifiable before you demo it** — a preflight script probes every corpus with
  latency, and 255 tests run with no network in the default tier.

## Quickstart

Everything below runs on a laptop, with nothing provisioned.

```bash
# 1. Clone the repository
git clone <repo-url> && cd URLvestigia

# 2. Run the reference app (the Serve layer)
make install
make dev                 # → http://127.0.0.1:8000/

# 3. Before a live demo: is this machine actually reaching every corpus?
make doctor              # probes each provider and web engine, with latency

# 4. The Harden gate
make test                # 255 passing, 13 skipped (the live tier)
```

**Without `make`** — the Makefile needs bash, so on Windows without Git Bash or WSL use
these directly. They are the same commands the targets wrap:

```bash
python -m pip install -r app/requirements.txt -r tests/requirements.txt
python -m uvicorn app.server:app --reload --port 8000
python scripts/doctor.py
python -m pytest tests -q
```

### Use the library directly

```python
from urlvestigia import text_to_urls

urls = text_to_urls("best python web scraping libraries", max_results=10)
```

Options: `provider` (`"ddgs"`, `"wikipedia"`, `"openalex"`, `"arxiv"`), `max_results`
(10), `region` (`"wt-wt"`, e.g. `"us-en"`, `"kr-kr"`), `safesearch` (`"on"` /
`"moderate"` / `"off"`), `timelimit` (`None`, `"d"`, `"w"`, `"m"`, `"y"`), and
`backend` — one engine or a comma-delimited fallback chain (`"duckduckgo,yahoo"`).
URLs come back deduplicated, in ranking order.

**Not every provider supports every option**, and the ones that don't apply are dropped
rather than silently ignored — `region` selects a Wikipedia language edition,
`timelimit` filters OpenAlex and arXiv by publication date, and neither `safesearch` nor
the engine chain means anything outside `ddgs`. The support matrix and the reasoning are
in [`retrieval/README.md`](retrieval/README.md).

## Architecture / Software Components

<img width="1351" height="717" alt="image (2)" src="https://github.com/user-attachments/assets/4a40b120-aa56-47b1-b40d-5e9623e5d845" />


A request enters the **Serve** layer — a FastAPI + Jinja2 dashboard rendered entirely
server-side, with no build step and no frontend framework. Every option is
whitelist-validated and every mutation is POST-redirect-GET. The **AI / retrieval**
layer resolves the request through `text_to_urls()`, which consults a support matrix to
decide which options the selected provider may legitimately be asked for, then calls the
corresponding corpus: `ddgs` for the open web (with a fallback chain across DuckDuckGo,
Yahoo, Startpage, and Yandex), or the keyless Wikipedia, OpenAlex, and arXiv APIs.

Results and the full option set are written to the **storage** layer. Today that is a
single SQLite file at `data/urlvestigia.db`, relocatable with the `URLVESTIGIA_DB`
environment variable — an accelerator has to run on a laptop before any CDP environment
exists. The designed second tier is **Apache Iceberg on CDW**, sharing the same schema
shape, with [`data/ingest/load_to_iceberg.py`](data/ingest/load_to_iceberg.py) as the
bridge. **Only links are stored, never page content.**

`make backup` — or the **Store** button in the app — takes a dated local snapshot of the
dev store, safe to take while the app is serving and never overwriting a previous one.

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the design system is
documented in [`docs/architecture/DESIGN_TEMPLATE.md`](docs/architecture/DESIGN_TEMPLATE.md).

### Cloudera services by layer

| Layer | Directory | Cloudera service | State |
|---|---|---|---|
| Serve | `app/` | Cloudera AI Application | runs locally; never published |
| AI | `retrieval/` | Cloudera AI Workbench | runs locally; never hosted |
| Ingest | `data/ingest/` | Cloudera Data Engineering | dry run only |
| Lakehouse | `data/iceberg/` | Iceberg on CDW / Data Lake | DDL written; never applied |
| Process | `pipelines/` | Cloudera Data Engineering | dry run only |
| Governance | `governance/` | SDX — Ranger, Atlas | policies written; never imported |

## Target Audience

- **Solution architects and SEs** who need a working, governed source-collection demo
  that runs on a laptop before any environment is provisioned.
- **Data engineers** assembling research or RAG corpora who need the collection step to
  be reproducible and queryable rather than ad hoc.
- **Data governance and compliance reviewers** evaluating whether an upstream collection
  step can be brought under Ranger policy and Atlas lineage.
- **Accelerator authors** using this repo as the Forge-standard template for a new
  vertical or use case.

No ML expertise is required. Familiarity with Python, FastAPI, and — for the platform
layers — CDP environment provisioning is assumed.

## Repository Structure

Every directory is present and documented, with its own `README.md` explaining what goes
there, the naming conventions, and which Cloudera API or tool automates it. The
right-hand column says which ones execute today.

| Path | Description | State today |
|---|---|---|
| `docs/` | Architecture, business case, gates, worked example | written |
| `infra/` | IaC — CDP CLI / Terraform | dry run, not provisioned |
| `data/` | SQLite dev store · Iceberg DDL · loader | SQLite runs, Iceberg planned |
| `pipelines/` | Data Engineering (Spark) jobs | dry run, needs Spark |
| `retrieval/` | `text_to_urls()`, search providers, eval notebook | runs |
| `app/` | FastAPI + Jinja2 dashboard (the Serve layer) | runs |
| `governance/` | SDX policies · model card · data classification | written, not imported |
| `tests/` | Data quality · retrieval eval, no network by default | 255 passing |
| `.cicd/` | build → test → deploy | dry run |
| `.github/` | The same test tiers, in Actions | runs on every push |
| `.gitlab/` | MR + issue templates | written |
| `scripts/` | `doctor.py` preflight · `new-accelerator.sh` | runs |
| `Makefile` | `make dev` · `make test` · `make backup` | runs (needs bash) |
| `METADATA.yaml` | Catalog metadata for the Cloudera blueprint website | **to be added** |

### Start a new accelerator from this template

```bash
make new VERTICAL=healthcare USECASE=readmission-risk
```

Copies the tracked layout into a sibling directory, clears this accelerator's worked
example while keeping every directory `README.md`, re-points the name, and initialises a
fresh git repo. Pass `--dry-run` to the script to print the plan first.

## Prerequisites

**To run the blueprint locally — nothing provisioned:**

| Requirement | Notes |
|---|---|
| Python 3.10 or later | Dependencies in `app/requirements.txt` and `tests/requirements.txt` |
| `git` | To clone the repository |
| bash | Only for the `make` targets — use the direct commands on Windows without Git Bash or WSL |
| Outbound HTTPS | To public search-engine pages and the Wikipedia, OpenAlex, and arXiv APIs |

**No API keys, no accounts, and no Docker are required for the local path.**

**To connect the platform layers — not yet executed:**

| Requirement | Notes |
|---|---|
| Cloudera platform access / entitlement | CDP environment with Data Lake |
| Cloudera Data Warehouse (CDW) | For the Iceberg tables |
| Cloudera Data Engineering (CDE) | For the ingest and enrichment jobs |
| Cloudera AI Workbench + AI Application | For hosting the retrieval and Serve layers |
| SDX — Ranger, Atlas | For policy import and lineage |
| CDP CLI or Terraform | Used by `infra/` |

## Hardware Requirements

| Deployment | Minimum |
|---|---|
| Laptop / demo | 2 vCPU, 4 GB RAM, 1 GB storage — no GPU |
| Production / enterprise | Sized by the CDP environment: CDW virtual warehouse and CDE virtual cluster per your platform team's standard. No GPU required — the blueprint runs no models. |

Storage grows with the number of recorded searches only. Page content is never stored,
so the corpus table stays small relative to the material it points at.

## Documentation

- [`docs/EXAMPLE.md`](docs/EXAMPLE.md) — one search traced across all five layers, ~20
  minutes on a laptop. **Start here.**
- [`docs/GATES.md`](docs/GATES.md) — the 6-phase stage gate and what "done" means at each
  phase.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the build standard and why the deploy
  order matters.
- [`docs/BUSINESS_CASE.md`](docs/BUSINESS_CASE.md) — the weighted scoring and business
  justification.
- [`retrieval/README.md`](retrieval/README.md) — the provider support matrix and its
  reasoning.
- [`data/README.md`](data/README.md#backups) — the dev store and snapshot behaviour.
- [`governance/DATA_CLASSIFICATION.md`](governance/DATA_CLASSIFICATION.md) — where query
  text goes and what that means for a customer.
- [`.cicd/README.md`](.cicd/README.md) — the standard deliverable and deploy sequence.

### The Forge standard

| Component | What it is | Read |
|---|---|---|
| A way to choose | Weighted scoring; ≥ 4.0 / 5 advances | [`.gitlab/issue_templates/`](.gitlab/issue_templates/Use-Case-Candidate.md) · [`BUSINESS_CASE.md`](docs/BUSINESS_CASE.md) |
| A build process | 6-phase stage gate, one accountable owner per phase | [`docs/GATES.md`](docs/GATES.md) |
| A build standard | Ingest → Lakehouse → Process → AI → Serve, governed by SDX | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| A standard deliverable | This repo | [`.cicd/`](.cicd/README.md) |

| Week | wk 0 | wk 1 | wk 2 | wk 3–6 | wk 7 | wk 8 |
|---|---|---|---|---|---|---|
| **Phase** | Discover | Qualify | Architect | Build | Harden | Publish → Deployed |

From selected use case to a deployed, governed solution. The Build phase scales with
complexity.

## Status

**Solid at the web edge.** The capability this blueprint exists to deliver — text in, a
governed table of URLs out, with the full option set recorded per search — is finished
and working. Four corpora, a support matrix that keeps every recorded option honest, 255
tests, and a dashboard that runs on a laptop with one command.

**The extension worth making next is storage.** SQLite is the right store for a single
analyst on one machine, and the wrong one past that: it serialises writes, so concurrent
users queue behind each other; it lives on one disk, so it does not survive the machine;
and it cannot be queried by BI tools or governed by SDX. Iceberg on CDP answers all three
— partitioned, concurrently readable, time-travelled, and covered by Ranger policy. The
schema shape, the DDL, the loader, and the enrichment job are already written against
that target; what remains is connecting them.

### Before hosting it

Three items are open, listed here rather than left to be discovered:

- **No authentication and no CSRF protection.** `/clear`, `/delete/{id}`, `/dedupe`, and
  `/store` act on an unauthenticated POST. Correct for `127.0.0.1`, wrong once the app is
  served to anyone else.
- **The retrieval model card carries no dated evaluation run.** Engine behaviour drifts,
  so the claim needs a date — run `retrieval/notebooks/eval.ipynb`.
- **`ingress_cidrs` defaults to `0.0.0.0/0`.** Fine for a sandbox, wrong anywhere else.

### A property of the design, not a gap

**Query text leaves the environment.** Searches go to third-party public endpoints with
no API key and therefore no data-processing agreement. Raise this first with any customer
whose data cannot leave. See
[`governance/DATA_CLASSIFICATION.md`](governance/DATA_CLASSIFICATION.md).

---

## Planned platform integration

**None of this section has run.** The CDP layers are designed, committed, reviewed, and
dry-run clean — every script prints the exact commands it would issue — but no part of it
has been executed against a real Cloudera environment. Treat it as an architecture
proposal with working scaffolding, not as a deployment. Connecting it is the next piece
of work.

Every target below prints what it *would* do and changes nothing:

```bash
make -n deploy           # the whole deploy, expanded
make provision           # one-time platform provisioning (dry run)
make ingest              # SQLite → Iceberg load plan
make pipelines           # URL enrichment plan, including the literal MERGE
make govern              # SDX / Ranger policy import plan
make help                # list all targets
```

Nothing in this repo changes a remote system without an explicit `--execute`.

Connecting it would mean, in order: provision a CDP environment
([`infra/`](infra/README.md)), apply the Iceberg DDL, import the Ranger policies, then
register the CDE jobs. `.cicd/deploy.sh` sequences exactly that, and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) explains why the order matters — access
control lands before data moves, and data lands before anything serves it.
