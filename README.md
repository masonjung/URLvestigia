# URLvestigia — Cloudera Forge Accelerator

**Natural-language text in, a governed table of URLs out.** Type a question, get a
persisted list of source links — with the query, provider, engines, region, and time
window stored alongside, so a search becomes an artifact instead of an activity.

Search the web, Wikipedia, OpenAlex, or arXiv. Each exposes only the options it
genuinely applies, and the record says which.

Free to run: no API keys, no accounts, no build step. The only external services it
talks to are public search-engine pages and three keyless non-profit APIs.

Built to the Cloudera Forge standard accelerator layout — Ingest → Lakehouse →
Process → AI → Serve. **Retrieval, Serve, and local storage are finished and run
today.** The CDP platform layers are written against the same schema but not yet
connected; extending storage from SQLite to Iceberg is the next step rather than a
missing one — see [Planned platform integration](#planned-platform-integration).

**New here?** Walk [`docs/EXAMPLE.md`](docs/EXAMPLE.md) — one search traced across all
five layers in about 20 minutes, on a laptop. Then use
[`docs/GATES.md`](docs/GATES.md) to know what "done" means at each phase.

## Quickstart

Everything below runs on a laptop, with nothing provisioned.

```bash
# 1. Run the reference app (the Serve layer)
make install
make dev                 # → http://127.0.0.1:8000/

# 2. Before a live demo: is this machine actually reaching every corpus?
make doctor              # probes each provider and web engine, with latency

# 3. The Harden gate
make test                # 255 passing, 13 skipped (the live tier)
```

**Without `make`** — the Makefile needs bash, so on Windows without Git Bash or WSL
use these directly. They are the same commands the targets wrap:

```bash
python -m pip install -r app/requirements.txt -r tests/requirements.txt
python -m uvicorn app.server:app --reload --port 8000
python scripts/doctor.py
python -m pytest tests -q
```

## How a search flows

![How a search flows](docs/img/search-flow.png)

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## The standard repo

Every directory is present and documented. The right-hand column says which ones
execute today.

```
URLvestigia/
├── docs/         architecture · business case          written
├── infra/        IaC — CDP CLI / Terraform             dry run, not provisioned
├── data/         SQLite dev store · Iceberg DDL        SQLite runs, Iceberg planned
├── pipelines/    Data Engineering (Spark) jobs         dry run, needs Spark
├── retrieval/    search providers · notebooks · eval   runs
├── app/          FastAPI + Jinja2 dashboard            runs
├── governance/   SDX policies · model card             written, not imported
├── tests/        data quality · retrieval eval         255 passing
├── .cicd/        build → test → deploy                 dry run
├── .github/      the same test tiers, in Actions       runs on every push
├── .gitlab/      MR + issue templates                  written
├── scripts/      doctor · new-accelerator.sh           runs
└── Makefile      make dev · make test                  runs (needs bash)
```

Each directory has a `README.md` explaining what goes there, the naming conventions,
and which Cloudera API/tool automates it.

## What's in here

- **`app/`** — a complete, working config-free dashboard: FastAPI + Jinja2, rendered
  entirely server-side with **no build step and no framework** — the only script is
  ~40 lines of inline progressive enhancement that spin the Search button while a
  search is in flight. Every option is
  whitelist-validated; every mutation is POST-redirect-GET. The design system is
  documented in [`docs/architecture/DESIGN_TEMPLATE.md`](docs/architecture/DESIGN_TEMPLATE.md).
- **`retrieval/`** — `text_to_urls()`, the whole capability behind one function, with four
  selectable corpora and a support matrix that decides what each one may be asked;
  plus an eval notebook that measures availability and overlap before you change a
  default.
- **`data/`** — the SQLite dev store every search is written to, plus the Iceberg DDL
  and the loader that will bridge to it.
- **`tests/`** — 255 tests across every layer, with no network in the default run.
- **`scripts/`** — `doctor.py`, the pre-demo preflight that probes every corpus, and
  `new-accelerator.sh`, which clones this template into a fresh accelerator repo.

## Use the library directly

```python
from urlvestigia import text_to_urls

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
and the reasoning are in [`retrieval/README.md`](retrieval/README.md).

## Storage

**Today, every search is written to SQLite** — a single file at
`data/urlvestigia.db`, moved with the `URLVESTIGIA_DB` environment variable. That is
the entire storage path that currently executes.

SQLite is not a placeholder: an accelerator has to run on a laptop before any CDP
environment exists. The designed second tier is **Apache Iceberg**, sharing the same
schema shape, with [`data/ingest/load_to_iceberg.py`](data/ingest/load_to_iceberg.py)
as the bridge — written, exercised against its own dry run, and not yet connected to
anything. See [Planned platform integration](#planned-platform-integration).

`make backup` — or the **Store** button in the app — takes a dated local snapshot of
the dev store, safe to take while the app is serving and never overwriting a previous
one. Details in [`data/README.md`](data/README.md#backups).

Only links are stored, never page content.

## Start a new accelerator from this template

```bash
make new VERTICAL=healthcare USECASE=readmission-risk
```

Copies the tracked layout into a sibling directory, clears this accelerator's worked
example while keeping every directory `README.md`, re-points the name, and
initialises a fresh git repo. Pass `--dry-run` to the script to print the plan first.

## The Forge standard

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

**Solid at the web edge.** The capability this accelerator exists to deliver — text
in, a governed table of URLs out, with the full option set recorded per search — is
finished and working. Four corpora, a support matrix that keeps every recorded option
honest, 255 tests, and a dashboard that runs on a laptop with one command.

**The extension worth making next is storage.** SQLite is the right store for a
single analyst on one machine, and the wrong one past that: it serialises writes, so
concurrent users queue behind each other; it lives on one disk, so it does not survive
the machine; and it cannot be queried by BI tools or governed by SDX. Iceberg on CDP
answers all three — partitioned, concurrently readable, time-travelled, and covered by
Ranger policy. The schema shape, the DDL, the loader, and the enrichment job are
already written against that target; what remains is connecting them. See
[Planned platform integration](#planned-platform-integration).

### Before hosting it

Three items are open, listed here rather than left to be discovered:

- **No authentication and no CSRF protection.** `/clear`, `/delete/{id}`, `/dedupe`,
  and `/store` act on an unauthenticated POST. Correct for `127.0.0.1`, wrong once the
  app is served to anyone else.
- **The retrieval model card carries no dated evaluation run.** Engine behaviour
  drifts, so the claim needs a date — run `retrieval/notebooks/eval.ipynb`.
- **`ingress_cidrs` defaults to `0.0.0.0/0`.** Fine for a sandbox, wrong anywhere
  else.

### A property of the design, not a gap

**Query text leaves the environment.** Searches go to third-party public endpoints
with no API key and therefore no data-processing agreement. Raise this first with any
customer whose data cannot leave. See
[`governance/DATA_CLASSIFICATION.md`](governance/DATA_CLASSIFICATION.md).

---

## Planned platform integration

**None of this section has run.** The CDP layers are designed, committed, reviewed,
and dry-run clean — every script prints the exact commands it would issue — but no
part of it has been executed against a real Cloudera environment. Treat it as an
architecture proposal with working scaffolding, not as a deployment. Connecting it is
the next piece of work.

| Layer | Directory | Cloudera service | State |
|---|---|---|---|
| Serve | `app/` | Cloudera AI Application | runs locally; never published |
| AI | `retrieval/` | Cloudera AI Workbench | runs locally; never hosted |
| Ingest | `data/ingest/` | Cloudera Data Engineering | dry run only |
| Lakehouse | `data/iceberg/` | Iceberg on CDW / Data Lake | DDL written; never applied |
| Process | `pipelines/` | Cloudera Data Engineering | dry run only |
| Governance | `governance/` | SDX — Ranger, Atlas | policies written; never imported |

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
([`infra/`](infra/README.md)), apply the Iceberg DDL, import the Ranger policies,
then register the CDE jobs. `.cicd/deploy.sh` sequences exactly that, and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) explains why the order matters —
access control lands before data moves, and data lands before anything serves it.
