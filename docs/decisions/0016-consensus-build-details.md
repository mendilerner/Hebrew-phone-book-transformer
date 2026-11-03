# 0016: Details of the consensus build

Date: 2026-11-03 · Status: Accepted · Builds: 0015

**Decision (build step 7):** small choices 0015 left open.
- **Graph:** `classify_page` → `read_claude` + `read_gpt` (a router returns both names,
  so they run in parallel) → `compare_reads` (a join: it waits for both) →
  `tie_break` → `verify` → `finalize_page`. Both readers write the new key `reads`,
  so it has the `add` reducer.
- **Models:** settings `tiers`: `read_claude` and `tie_break` = `best` (Opus),
  `read_gpt` and `verify` = `gpt` (`openai:gpt-6-astra`), `classify_page` = `cheap`.
  `--tier` in `cli_page` changes only the Claude nodes.
- **No confidence threshold:** agreement decides, not the model's own confidence.
  The setting `min_confidence` is removed. Free rule checks (`check_contact`) still
  send any entry to review, also an agreed one.
- **Entry only one reader found** → review (`issues`: "only claude read this entry").
- **Pointing at a row:** the first shared phone; with no shared phone, the row number.
- **A and B alternate** between doubts, so the tie-breaker can't learn "A is always Claude".
- **New `Contact` fields:** `source` (agreed / tie-breaker / human; empty = review) and
  `readings` (every reader's text). The Excel gets a `source` column.

**Why:** the simplest choices that keep the 0015 rule: a name reaches the Excel only
when two models agree on it.
