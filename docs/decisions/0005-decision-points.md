# 0005: Where the agent makes choices

Date: 2026-10-12 · Status: Accepted

**Decision:** Use three kinds of decisions on purpose: rule routers (R),
LLM routers (L), and a ReAct agent inside the page-reading node (A).
The 8 decision points are listed in `docs/ARCHITECTURE.md`.
Every loop has a max-attempts counter. Every decision is logged with its reason.

**Consequences:** Covers all main LangGraph routing styles. Costs stay limited.
