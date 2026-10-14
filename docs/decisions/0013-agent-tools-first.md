# 0013: Agent tools before the book graph

Date: 2026-10-14 · Status: Accepted

**Context:** real runs of the simple page graph read Hebrew letters badly, even
with Opus. The page was shrunk to 1568 px, so handwriting was small.

**Decision:**
- Build step 6 (agent tools) before step 5 (book graph), because reading quality
  is the main problem now.
- Pages go out at up to 2576 px (the 5.x models read that size). Crops are cut
  from the full-resolution photo; small crops are made bigger.
- `find_row_lines` (OpenCV) finds the printed lines. The page the agent sees has
  row numbers in a white strip on the left, so the agent and the tools use the
  same row numbers. No lines found → the agent counts rows and uses `crop_region`.
- `row_view` zoom = the row in two pictures (right half, left half), so each
  half gets more pixels.
- `read_page` = `create_agent` with `ProviderStrategy(PageRead)` (native JSON, no
  forced tool call, see 0010) and `ToolCallLimitMiddleware(run_limit=agent_tool_calls)`.
- The cost of `read_page` is the sum of all the agent's model turns.
- The first real run: the model answered at once and used no tool, though every
  entry had a low confidence. So a small middleware (`check_before_answer`, an
  `after_model` hook) sends it back **once** with the least sure rows, using
  `jump_to="model"`. The prompt also asks it to check unclear rows first.

**Cost:** bigger images use more input tokens (up to about 3×), and each tool call
is one more model turn. Max 4 calls per page keeps it bounded.
