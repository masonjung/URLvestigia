# Model card — T2URL retrieval

| | |
|---|---|
| **Component** | `ai/t2url.py` → `text_to_urls()` |
| **Version** | Tracked by git commit; no separate model version |
| **Owner** | Accelerator owner (see [`docs/GATES.md`](../../docs/GATES.md)) |
| **Status** | Reference implementation, not customer-deployed |
| **Last reviewed** | Not yet reviewed — due at the Harden gate |

## What this is, and what it is not

**It is a metasearch client, not a trained model.** There are no weights, no
training data, no fine-tuning, and no inference of the customer's own. T2URL sends
a query to third-party search engines through the `ddgs` library and returns the
URLs they rank.

It gets a model card anyway, because from a governance standpoint it behaves like
one: an opaque third-party system converts user text into ranked output that drives
downstream decisions, and neither the ranking function nor its failure modes are
inspectable. The accountability questions are identical even though the mechanism
is not.

If retrieval later grows a genuine model — an LLM reranker, query expansion, an
agent loop — that component needs its **own** card. Do not extend this one.

## Intended use

Discovery and research: turning a natural-language information need into a
navigable set of source links, with the query and its options recorded so the search
is reproducible.

**Out of scope, explicitly:**

- **Exhaustive retrieval.** Results are what a public engine ranked in the top N.
  Absence of a URL is not evidence the page does not exist. Never use T2URL output
  to conclude "there is no such document."
- **Ranking as authority.** `best_position` reflects engine SEO ranking, not
  credibility, recency, or correctness.
- **Compliance or legal search** where completeness is a requirement.
- **Any deployment where query text cannot leave the environment** — see
  [`../DATA_CLASSIFICATION.md`](../DATA_CLASSIFICATION.md#third-party-disclosure).

## Inputs and outputs

**In:** natural-language text, plus `max_results` (1–50), `region`, `safesearch`,
`timelimit`, `backend`. Every option is whitelist-validated in `app/server.py`
before it reaches this component.

**Out:** a list of URL strings, deduplicated, in engine rank order. Empty list when
no engine returns anything — which is indistinguishable from "no such page exists,"
and is the component's most important failure mode.

## Known limitations and risks

| Risk | Detail | Mitigation |
|---|---|---|
| **Silent empty results** | A throttled engine returns `[]`, identical to a genuine no-match | Fallback chain across up to four engines; `app/server.py` surfaces "No results found" rather than an empty success |
| **Third-party ranking bias** | Engine ranking encodes commercial SEO and each provider's own editorial choices. T2URL inherits all of it and cannot inspect it. | Multi-engine chain reduces single-provider dependence; overlap measured in `ai/notebooks/retrieval_eval.ipynb` |
| **Geographic and language skew** | `region` materially changes results; `wt-wt` default skews English | Region is user-selectable and recorded per search |
| **Non-reproducibility** | Engines re-rank continuously. The same query tomorrow returns different URLs. | Every search persists its full option set and timestamp, so a result set is explainable even when it is not repeatable |
| **Availability drift** | Engines add rate limits and blocks without notice | Re-run the eval notebook before changing defaults; treat availability as a monitored property |
| **No content safety on targets** | `safesearch` is applied by the engine; T2URL does not inspect the pages | Defaults to `moderate`; never fetches page content |
| **Yandex data residency** | Operated from Russia; excluded by some customers' rules | Off by default in the UI |

## Evaluation

Measured by [`ai/notebooks/retrieval_eval.ipynb`](../../ai/notebooks/retrieval_eval.ipynb) —
availability, mean yield, and pairwise engine overlap.

> **No results recorded yet.** Run the notebook and paste the availability and
> overlap tables below with the date. Engine behaviour drifts, so an undated
> measurement is not evidence — a result older than a quarter should be re-run
> before it is relied on.

| Date | Engine | Availability | Mean yield | Notes |
|---|---|---|---|---|
| _pending_ | duckduckgo | — | — | Current default |
| _pending_ | yahoo | — | — | |
| _pending_ | startpage | — | — | |
| _pending_ | yandex | — | — | Off by default |

The gate for changing the default `backend` chain is in
[`docs/GATES.md`](../../docs/GATES.md) under **Harden**.

## Ethical and operational considerations

T2URL queries public endpoints without an API key or account. That makes it free to
run and free of vendor lock-in; it also means usage is bounded by each provider's
tolerance rather than by a contract. The `COOLDOWN_S` pause in the eval notebook and
the 50-result ceiling in `app/server.py` exist for that reason. Removing them shifts
cost onto providers who have not agreed to carry it.

Users see the URLs, not the mechanism. The Serve layer records and displays which
engine, region, and time window produced each result set — keep that visible if the
UI is rebuilt.

## Change log

| Date | Change | Rationale |
|---|---|---|
| 2026-08-04 | Card created during the Forge layout restructure | Retrieval had no governance record |

Record every change to a retrieval default here, with the eval run that justified it.
