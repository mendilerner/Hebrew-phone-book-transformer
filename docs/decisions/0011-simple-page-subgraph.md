# 0011: Simple page sub-graph

Date: 2026-10-14 · Status: Accepted

**Decision (build step 4):**
- `classify_page` → `read_page` → `finalize_page`. Empty and cover pages end
  right after `classify_page` (no read call, saves money).
- `different_layout` pages: the MVP has no `rediscover_layout`, so the page is
  read with the book layout and every entry goes to the review queue.
- The LLM returns `EntryDraft` (raw phone text, its own doubts, a confidence).
  Python turns it into `Contact` with `parse_phone`, so phone rules stay in code.
- `finalize_page` splits: any issue or `confidence < min_confidence` (new setting,
  default 0.8) → `review_queue`; else → `contacts`.
- `read_page` is one LLM call for now. Agent tools come in build step 6.

**Why:** the simplest page graph that already gives real output, so we can measure
reading quality on real pages before we add the agent and the retry loop.
