<!-- A candidate accelerator, for scoring at the Qualify gate.
     Score ≥ 4.0 / 5 advances. See docs/GATES.md §Qualify. -->

/label ~"use-case-candidate" ~"forge::discover"

## The use case

**Vertical:**
**Customer / segment:**
**One sentence:**

<!-- What does someone do differently on the day this exists? -->

## The problem today

<!-- How is this handled now, and what does that cost? Be concrete — a number
     here is worth a paragraph of adjectives. -->

## Why Cloudera

<!-- What about this needs the platform? If it runs fine as a laptop script,
     say so — that is a legitimate answer and a fast disqualification. -->

## Scorecard

Score each 1–5. **Weighted total ≥ 4.0 advances to Qualify.**

| Criterion | Weight | Score | Justification |
|---|---:|---:|---|
| **Market demand** — how many customers ask for this | 25% | | |
| **Revenue impact** — pipeline it influences | 25% | | |
| **Technical fit** — uses the reference stack as designed | 20% | | |
| **Reusability** — how much survives the next customer | 20% | | |
| **Effort** — inverse; 5 = weeks, 1 = quarters | 10% | | |
| **Weighted total** | | | |

<!-- Reusability is the one people inflate. A demo rebuilt from scratch for
     every customer is not an accelerator, whatever else it scores. -->

## Reference stack fit

Which layers does this actually use? Gaps are fine — say so.

- [ ] **Ingest** — DataFlow / batch load
- [ ] **Lakehouse** — Iceberg tables
- [ ] **Process** — Spark / Data Engineering
- [ ] **AI** — Cloudera AI, NIM, agents
- [ ] **Serve** — dashboard or API
- [ ] **Governed by SDX** — policies, lineage, model cards

## Data

**Source(s):**
**Anything sensitive?**
**Can it leave the customer's environment?**

<!-- Answer the third one before Architect, not after. It has killed accelerators
     at the Harden gate that were fine everywhere else. -->

## Proposed owner

<!-- One accountable name per phase. Not a team. -->

| Phase | Owner |
|---|---|
| Discover | |
| Qualify | |
| Architect | |
| Build | |
| Harden | |
| Publish | |

## Effort

**Estimated build:** <!-- weeks; the standard lifecycle is ~8 -->
**What would make it longer:**

## Decision

<!-- Filled in at the Qualify gate. -->

- [ ] **Advance** — score ≥ 4.0, owner assigned, Architect starts
- [ ] **Hold** — good idea, wrong quarter. Reason:
- [ ] **Decline** — reason:
