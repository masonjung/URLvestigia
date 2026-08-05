# `data/` — Ingest + Lakehouse layers

Where search results land and where they live. Two storage tiers, same shape:

| Tier | Store | Used by |
|---|---|---|
| **Local / dev** | SQLite, one file at `data/t2url.db` | `app/server.py` via `db.py` — the default when you `make dev` |
| **Platform** | Apache Iceberg tables in the CDP lakehouse | `pipelines/`, BI tools, anything past a single node |

SQLite is not a placeholder for Iceberg — it is the demo path. An accelerator has to
run on a laptop during Discover, before any CDP environment exists. `ingest/load_to_iceberg.py`
is the bridge between the two.

## What's here

| Path | What it is |
|---|---|
| `db.py` | SQLite persistence. **All application SQL lives here** — no other module writes SQL against the dev store. |
| `schema.sql` | The SQLite schema: `searches`, `search_urls`, one index |
| `iceberg/ddl.sql` | Iceberg DDL for the platform tier: `raw_searches`, `raw_search_urls`, `curated_urls` |
| `ingest/load_to_iceberg.py` | Loads the SQLite dev store into the raw Iceberg tables |
| `t2url.db` | The database itself — **gitignored**, created on first run |

## The model

One search produces N URLs. That parent/child shape is identical in both tiers:

```
searches / raw_searches          one row per query, plus the options that produced it
   └── search_urls / raw_search_urls    one row per result URL, with its rank position
           └── curated_urls             pipelines/ output: deduplicated + domain-enriched
```

`created_at` is stored as an **ISO-8601 UTC string** (`datetime.now(timezone.utc).isoformat()`).
The Serve layer converts to local time for display only. Do not store local time.

## Run it

```bash
make ingest                                    # dry-run: prints the load plan and row counts
python data/ingest/load_to_iceberg.py --execute   # real load, needs Spark + Iceberg catalog
```

Move the dev database anywhere with the `T2URL_DB` environment variable:

```bash
T2URL_DB=/tmp/scratch.db make dev
```

## Conventions

- **Only links are stored, never page content.** T2URL records URLs and the query
  that produced them. It does not fetch, cache, or persist the pages themselves.
  This is a governance commitment, not an implementation detail — see
  [`governance/DATA_CLASSIFICATION.md`](../governance/DATA_CLASSIFICATION.md).
- **`db.py` owns every statement.** If SQL appears in `app/` or `ai/`, it is in the
  wrong file.
- **Deletes cascade.** `search_urls.search_id` is a `REFERENCES … ON DELETE CASCADE`
  foreign key and `db.py` enables `PRAGMA foreign_keys = ON` on every connection —
  SQLite ignores the constraint otherwise. Keep that pragma when adding connections.
- **Additive migrations only.** `init_db()` runs `schema.sql` (all `IF NOT EXISTS`)
  then `ALTER TABLE … ADD COLUMN` for anything missing, so an existing database
  upgrades in place. Add new columns to *both* `schema.sql` and that migration list.
- **Iceberg schema changes go through the DDL file**, never an ad-hoc `ALTER` from a
  notebook. Iceberg schema evolution is tracked in table metadata; keeping the DDL
  authoritative is what makes the lineage in Atlas readable.

## Which Cloudera tool automates it

- **Ingest** — Cloudera **DataFlow** (NiFi) for continuous collection, or
  `ingest/load_to_iceberg.py` submitted as a **Cloudera Data Engineering** job for
  scheduled batch loads. T2URL's volume is small enough that batch is the honest
  default; DataFlow earns its place when searches arrive from a live feed rather
  than a form.
- **Lakehouse** — Iceberg tables on **CDW** / **CDP Data Lake** storage, created by
  `iceberg/ddl.sql`. Governed by SDX: policies in
  [`governance/sdx/`](../governance/sdx/), lineage captured automatically in Atlas.
