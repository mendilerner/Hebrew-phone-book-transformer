# 0009: MVP scope

Date: 2026-10-12 · Status: Accepted

Also: decision 0008 (tool list) was accepted when PR #6 was merged.

**MVP goal:** one full book in → Excel + `.vcf` out, using every main LangGraph concept.

**In the MVP:**
- Book graph: `load_book` → `discover_layout` → `confirm_layout` ⏸ → Send one
  page sub-graph per page → `human_review` ⏸ → `export`.
- Page sub-graph: `classify_page` (L) → `read_page` (agent) → `grade_entries` (R)
  → `choose_fix` (L) → `reread_row` (Send) → `page_fix` (R) → `finalize_page`.
- Model ladder: models per node from `config["configurable"]`; cheap first,
  stronger model as one of the fixes in `choose_fix`.
- Cost: `cost_usd` + budget, LLM answer cache, 3-page test set.

**Later (after the MVP):** `rediscover_layout`, `find_duplicates`, saving the
profile in the `Store` (MVP keeps it in the state), Batch API.

**Build order** (no time per step; each step ends with something that runs):
1. Project setup (package, settings, LLM cache, cost tracking).
2. Free helpers with unit tests: `parse_phone`, `rule_checks`, `export_excel`, `export_vcf`.
3. `discover_layout` + `confirm_layout` (structured output, `interrupt`, checkpointer).
4. Page sub-graph, simple: `classify_page` → `read_page` → `finalize_page`.
5. Book graph: `Send` per page + reducers (`contacts`, `cost_usd`).
6. Agent tools + `ToolCallLimitMiddleware` in `read_page`.
7. `grade_entries` → `choose_fix` → `reread_row` loop, with the model ladder and budget.
8. `page_fix`.
9. `human_review` + `export`; run the full book and measure the real cost.

**Consequences:** All three decision kinds (R, L, A) and the retry loop are in
the MVP. Duplicates are not removed in the MVP.
