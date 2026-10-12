# 0006: State schema

Date: 2026-10-12 · Status: Accepted (draft in `docs/design/state_schema.py`)

**Decision:** Pydantic models for data (LLM structured output), TypedDict for
graph state. Two levels: `BookState` (parent) and `PageState` (page sub-graph).
`contacts`, `review_queue` and `decisions` use the `add` reducer and the same
names in both states, so parallel page results are appended automatically.
Images are file paths, not bytes. No extra `Contact` fields (relation, category) for now.

**Consequences:** No mapping code between graphs. Checkpoints stay small.
