# Architecture

Status: **building the MVP** (steps 1-4 done: setup, free helpers, layout discovery, simple page sub-graph). Last update: 2026-10-12.

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
  read the page (ReAct agent, one read + max 4 tool calls) -> draft entries
  grade each entry (rules first, LLM only if unsure)
    -> accept / retry (pick a fix) / stronger model / review queue
    -> no retries when the page budget is used up
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
| 4 | Grade entry | accept / retry / stronger model / human (also checks budget) | R |
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

Code: [`src/phonebook/schema.py`](../src/phonebook/schema.py) (was the draft `docs/design/state_schema.py`).

- Pydantic models for data: `LayoutProfile`, `Contact`, `Phone`, `Decision`.
  A `Decision` from an LLM node also keeps its `model` and `cost_usd`
  ([decision 0012](decisions/0012-model-choice-per-run.md)).
- TypedDict for graph state: `BookState` (parent), `PageState` (sub-graph).
- `contacts`, `review_queue`, `decisions` use the `add` reducer, so parallel
  pages append results. Same key names in both states → passed up automatically;
  page-only keys (`skeleton`, `draft`, `attempts`) stay private.
- Images are stored as file paths, not bytes.
- `BookState.layout_clear` (bool): `discover_layout`'s answer, read by its router
  ([decision 0010](decisions/0010-layout-discovery-loop.md)).
- `cost_usd` (float, `add` reducer) sums the cost of every LLM call;
  `budget_usd` (book) and `page_budget_usd` (page) limit it.

## Cost control

See [decision 0007](decisions/0007-cost-control.md). In short:

- One LLM read per page; only flagged rows are read again.
- Free Python checks before any LLM grader.
- Models come from config (`config["configurable"]`): cheap first, strong only as a fix.
  Tiers: `cheap` = Haiku, `strong` = Sonnet, `best` = Opus (only when a run asks for it;
  the CLIs have `--tier`).
- `read_page` agent: max 4 tool calls, small crops, cached prompt + profile.
- Budget: default **$10 per book**, split into a share per page. Over budget → review queue.
- Development: LLM answer cache on disk, 3-page test set, Batch API for full runs.

## Tools

See [`docs/design/tools.md`](design/tools.md) (proposed in decision 0008).
Agent tools only in `read_page`: `row_view`, `crop_region`, `ink_crosses_line`,
`check_phone`. Everything else is a free Python helper or one LLM call with
structured output.

## Output rules

- Phone numbers are kept as written (`raw`). 7-digit numbers get **no** area code added.
- Unknown columns go to `Contact.extra`.

## MVP scope

See [decision 0009](decisions/0009-mvp-scope.md). Everything above is in the MVP
except `rediscover_layout`, `find_duplicates`, the `Store` (the profile stays in
the state), and the Batch API.

## Page reading rules (MVP)

See [decision 0011](decisions/0011-simple-page-subgraph.md).
- The LLM copies phones as raw text; Python (`parse_phone`) decides digits and kind.
- An entry goes to `review_queue` if it has any issue (LLM doubt or rule check)
  or `confidence < min_confidence` (setting, default 0.8). Otherwise to `contacts`.
- `different_layout` pages: read with the book layout, every entry goes to review
  (no `rediscover_layout` in the MVP).

## Code layout

- `src/phonebook/settings.py`: defaults (model ladder, tier per node, budget, cache path).
  Any value can be changed per run with `config["configurable"]`.
- `src/phonebook/llm.py`: `get_model(node, config, tier)` picks the model for a node.
- `src/phonebook/cost.py`: `cost_usd(answer, model)` from token usage; cached answers cost 0.
- `src/phonebook/llm_cache.py`: dev-mode disk cache for LLM answers.
- `src/phonebook/schema.py`: data models and graph states (moved from `docs/design/`).
- `src/phonebook/phones.py`: `parse_phone(raw)` → `Phone` (Israeli number rules).
- `src/phonebook/rules.py`: `check_contact`, `letter_order_issues` (free checks).
- `src/phonebook/images.py`: `list_pages`, `image_block` (upright, max 1568 px, JPEG).
- `src/phonebook/layout.py`: `load_book`, `discover_layout`, `add_sample_page`,
  `confirm_layout` (interrupt) and the router `route_after_discover`.
- `src/phonebook/book_graph.py`: `build_book_graph()` (layout part so far).
- `src/phonebook/cli.py`: run the graph in the terminal and answer the interrupt.
- `src/phonebook/page.py`: `classify_page` (LLM router), `read_page` (one LLM call for
  now), `finalize_page` (rule checks; good → `contacts`, doubtful → `review_queue`).
- `src/phonebook/page_graph.py`: `build_page_graph()`.
- `src/phonebook/cli_page.py`: read one page with the saved layout; `--tier` picks the
  model; saves the full result to `output/<page>.<tier>.json` (gitignored).
- `src/phonebook/export.py`: `export_excel` (phones as text) and `export_vcf`
  (only contacts with a mobile number).

## Not decided yet

Which model per node (measure on the 3-page test set).
