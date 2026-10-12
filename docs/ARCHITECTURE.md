# Architecture

Status: **design phase** (no code yet). Last update: 2026-10-12.

## Goal

Read photos of handwritten Hebrew phone books and output structured contacts
as Excel and `.vcf`. The output format is fixed. The input layout is **learned
per book**, so books with other columns or layouts work without code changes.

## Main flow

```
BOOK GRAPH (parent)
  discover_layout (2-3 sample pages) -> LayoutProfile
    -> unclear?  look at more pages (loop)
    -> human confirms / fixes the profile (interrupt), saved in the Store
  fan out: Send one PAGE SUB-GRAPH per page (parallel)
  merge contacts -> find duplicates -> human review (one batch per book)
  export Excel + .vcf

PAGE SUB-GRAPH (one per page)
  check the page against the profile -> entries / empty / cover / different layout
  read the page (ReAct agent with image tools) -> draft entries
  grade each entry -> accept / retry (pick a fix) / second model / review queue
  page fix: split entries across rows, letter order -> re-read only those rows
```

## Decision points

Three kinds of decisions are used on purpose (for learning):
**R** = rule router (Python function on a conditional edge),
**L** = LLM router (structured output picks the next node),
**A** = agent loop (ReAct agent with tools inside a node).

| # | Where | Choices | Kind |
|---|---|---|---|
| 1 | Layout discovery | clear → human confirm / unclear → more pages | R |
| 2 | Page check | fits → continue / different → re-discover / empty or cover → skip | L |
| 3 | Reading a page | agent uses tools (crop, zoom, "ink crosses line?", read region) | A |
| 4 | Grade entry | accept / retry / second model / human | R |
| 5 | Pick retry fix | grader says why it failed → matching fix | L |
| 6 | Page fix | split entry or wrong letter order → re-read those rows | R |
| 7 | Human review | batch all doubtful entries, ask once per book | R + interrupt |
| 8 | Duplicates | merge automatically / ask | L |

Safety rules: every loop has a max-attempts counter in the state, and every
decision is logged in `decisions` with its reason.

## Reading strategy

Never rely on one way of cutting the image: handwriting crosses the row lines.
The page is always read whole first (a "skeleton"). Then rows are checked with
views chosen per row: padded strip, 3-row window with the current row marked,
or zoom. See [decision 0003](decisions/0003-flexible-row-reading.md).

## State

Draft: [`docs/design/state_schema.py`](design/state_schema.py).

- Pydantic models for data: `LayoutProfile`, `Contact`, `Phone`, `Decision`.
- TypedDict for graph state: `BookState` (parent), `PageState` (sub-graph).
- `contacts`, `review_queue`, `decisions` use the `add` reducer, so parallel
  pages append results. Same key names in both states → passed up automatically;
  page-only keys (`skeleton`, `draft`, `attempts`) stay private.
- Images are stored as file paths, not bytes.

## Output rules

- Phone numbers are kept as written (`raw`). 7-digit numbers get **no** area code added.
- Unknown columns go to `Contact.extra`.

## Not decided yet

Graph topology details, tool list, MVP scope, model choice.
