# 0003: Read rows in more than one way

Date: 2026-10-01 · Status: Accepted

**Context:** Cutting the page into tight row strips made LLM results worse,
because letters and digits cross the row lines.

**Decision:** Always read the whole page first (skeleton). Then check rows with
views chosen per row: padded strip, 3-row window with the current row marked,
or zoom. A cheap image check ("does ink cross this line?") helps the agent choose.

**Consequences:** No single cut can lose text. More calls for hard rows only.
