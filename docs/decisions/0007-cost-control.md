# 0007: Cost control

Date: 2026-10-12 · Status: Accepted

**Problem:** A book has 400-500 contacts. With many LLM calls per row on a
strong model, one run can cost about $40-80 (estimate, not measured). During
development we run the pipeline many times, so cost can kill the project.

**Decision:**
1. **Read per page, not per row.** One LLM read per page. Only flagged rows are
   read again.
2. **Free checks first.** `grade_entries` runs Python rules first (digit count,
   empty name, letter order). It calls an LLM only when the rules can't decide.
3. **Model ladder from config.** Each LLM node takes its model from
   `config["configurable"]` (not hard-coded). Cheap model by default; the strong
   model only as a fix in `choose_fix`.
4. **Cap the agent.** `read_page` has max 4 tool calls. Tools send small crops,
   not the full page again. The system prompt and `LayoutProfile` are cached
   (prompt caching).
5. **Budget in the state.** `cost_usd` (float, `add` reducer) is summed from every
   LLM call. `budget_usd` per book (default **$10**, the user wants to lower it
   later). Each page gets a fair share (`page_budget_usd`). Over budget → no more
   retries, the row goes to `review_queue`.
6. **Development mode.** An LLM answer cache on disk (same input → saved answer,
   $0). A small test set of 3 pages. Full runs may use the Batch API (50% cheaper).

**Consequences:** Target cost about $1-3 per book on a mid model (estimate).
A new conditional edge (budget) in the page sub-graph. Pages run in parallel,
so a page can't see the live total of other pages; this is why each page gets
its own share.
