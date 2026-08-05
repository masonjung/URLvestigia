# T2URL — Data classification

What this accelerator stores, what it deliberately does not, and how each field is
classified. This is the document a customer's data-protection reviewer reads first.

## The one-line commitment

**T2URL stores links, never page content.** It records the query a user submitted
and the URLs a search engine returned. It does not fetch, render, cache, or persist
the pages behind those URLs.

That is enforced structurally, not by policy: `ai/t2url.py` reads only the `href`
field from each result and discards the rest of the response. There is no HTTP
client anywhere in this repo that fetches a result page. Any change that adds one
is a classification change and needs this document updated first.

## Inventory

| Field | Table | Classification | Why |
|---|---|---|---|
| `query` | `raw_searches` | **Confidential** | Free text typed by a user. Users put anything in a search box — assume it can contain personal or commercially sensitive detail even though the UI never asks for it. |
| `created_at` | `raw_searches` | Internal | Behavioural timestamp. Combined with `query`, reveals a user's activity pattern. |
| `region`, `safesearch`, `timelimit`, `backend`, `max_results` | `raw_searches` | Internal | Configuration, not user data. `region` is a weak locality signal. |
| `url` | `raw_search_urls`, `curated_urls` | Public | Public web addresses returned by a public search engine. |
| `position` | `raw_search_urls` | Public | Engine ranking. |
| `domain`, `tld`, `scheme` | `curated_urls` | Public | Derived from `url`. |
| `times_seen`, `first_seen`, `last_seen`, `best_position` | `curated_urls` | Internal | Aggregate popularity across searches. |

**The sensitive column is `query`, and only `query`.** Everything else is public web
data or configuration. Access control should be designed around that single fact —
see `sdx/ranger-policies.json`, which masks `query` for the analyst role while
leaving the URL tables readable.

## Personal data

T2URL as shipped stores **no identity fields**: no user ID, no session ID, no IP
address, no authentication subject. A search cannot be attributed to a person from
the data alone.

This is a real property of the current schema, and it is fragile. Adding a
`user_id` column — the obvious next feature for a multi-tenant deployment — changes
this accelerator's data-protection posture materially. If you add one:

1. Classify it **Confidential** and update this table.
2. Add a Ranger masking policy for it alongside the `query` policy.
3. Add a retention job — attributable search history needs a defined lifespan.
4. Re-run the Harden gate in [`docs/GATES.md`](../docs/GATES.md).

## Third-party disclosure

Queries are sent to external search engines (DuckDuckGo, Yahoo, Startpage, Yandex)
over their public endpoints. **The query text leaves the customer's environment.**

There is no API key and no account, so there is no contractual data-processing
agreement with these providers, and their handling is governed by their own privacy
policies rather than the customer's. For deployments where query text cannot leave
the environment, T2URL is not appropriate without swapping `ai/t2url.py` for an
internal index.

Note that Yandex is operated from Russia. Some customers' data-residency rules
exclude it outright; it is off by default in the UI and should stay off unless a
customer explicitly enables it.

## Retention

| Store | Default retention | Mechanism |
|---|---|---|
| SQLite dev store (`data/t2url.db`) | None — grows until cleared | `Clear all` in the UI, or delete the file |
| `raw_searches`, `raw_search_urls` | 7 days of Iceberg snapshots | `history.expire.max-snapshot-age-ms` in `data/iceberg/ddl.sql` |
| `curated_urls` | Indefinite | Aggregated public data, no expiry configured |

Snapshot expiry governs *time travel*, not the rows themselves — expiring snapshots
does not delete current data. **There is no row-level retention policy on
`raw_searches` today.** A deployment with a query-retention requirement needs a
scheduled `DELETE FROM t2url.raw_searches WHERE created_at < …` job added to
`pipelines/`; that is a known gap, not an oversight.

## Lineage

Atlas captures lineage automatically for the Spark paths:

```
search engines → ai/t2url.py → SQLite → data/ingest/load_to_iceberg.py
    → raw_searches / raw_search_urls → pipelines/jobs/url_enrichment.py
    → curated_urls
```

The first hop is outside Atlas's view — the engine call is an ordinary HTTPS request
from the Serve layer, so provenance for "which engine produced this URL" comes from
the `backend` column on `raw_searches`, not from lineage metadata. Keep that column
populated.
