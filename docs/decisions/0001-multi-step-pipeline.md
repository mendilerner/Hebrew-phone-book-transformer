# 0001: Multi-step LangGraph pipeline, not one LLM call

Date: 2026-10-01 · Status: Accepted

**Context:** Single calls to LLMs or OCR models did not read handwritten Hebrew well enough.

**Decision:** Build a "graph of loops": a fixed overall flow, with real choices
(routers and an agent) inside it. Vision LLMs do the reading.

**Consequences:** More calls and cost per page, but each step can be checked and retried.
