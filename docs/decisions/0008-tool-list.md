# 0008: Tool list

Date: 2026-10-12 · Status: Proposed (waiting for OK)

**Decision:** See [`docs/design/tools.md`](../design/tools.md).
- Only `read_page` has real agent tools: `row_view`, `crop_region`,
  `ink_crosses_line`, `check_phone` (max 4 calls, from 0007).
- Everything that can be done without an LLM is a plain Python helper
  (phone parsing, rule checks, row lines, export, cost tracking).
- Other LLM steps are single calls with structured output, not agents.
- The agent is the prebuilt `create_agent` (user's choice) with
  `ToolCallLimitMiddleware(run_limit=4)` for the cost limit. A hand-written loop
  (`ToolNode` + `tools_condition`) was the other option: more visible, more code.

**Consequences:** Few paid calls. Helpers can be unit-tested without an API key.
