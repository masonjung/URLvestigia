# `docs/img/` — exported diagrams

Rendered diagram images referenced from the Markdown. Source ASCII versions were
removed when these replaced them, so **the image is the diagram now** — if one is
missing, the document has a hole rather than a fallback.

| File | Referenced from | What it must show |
|---|---|---|
| `search-flow.png` | [`README.md`](../../README.md) | One search, end to end |
| `architecture-stack.png` | [`ARCHITECTURE.md`](../ARCHITECTURE.md) | The five layers and the two storage tiers |

## What `search-flow.png` must get right

Three things are easy to draw wrongly, and each one misrepresents a decision the
code deliberately makes:

- **Options are filtered *by* the provider, not merged after it.** The search
  options are an input, chosen alongside the query, and `SUPPORTS` in
  [`retrieval/providers.py`](../../retrieval/providers.py) drops the ones the
  selected provider does not apply. Drawing every provider converging on one
  shared "options" node inverts this — and that filtering is the single most
  distinctive thing the program does.
- **arXiv and OpenAlex are exclusive siblings, not a fan-out.** One search uses
  exactly one provider. Only the four web engines inside `ddgs` are genuinely
  queried together. Drawing both with the same fan-out shape gives them opposite
  semantics under identical arrows.
- **The batch tier is a separate flow, not part of the request.** The synchronous
  path ends at SQLite. Iceberg is reached later by a scheduled job — and today
  that job has never run against a real environment (see "Planned platform
  integration" in the README).

## Conventions

- **PNG, exported at 2× for legible text.** These are read on a projector.
- **Readable in greyscale.** Colour may carry emphasis, never meaning on its own.
- **Re-export rather than edit the PNG.** Keep the editable source wherever it
  lives; a diagram that can only be changed by drawing over it is frozen.
