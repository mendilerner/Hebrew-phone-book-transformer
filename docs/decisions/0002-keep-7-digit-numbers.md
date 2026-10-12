# 0002: Keep 7-digit phone numbers as written

Date: 2026-10-01 · Status: Accepted

**Context:** Old entries have 7-digit numbers with no area code (for example `5862723`).

**Decision:** Do not add an area code. Keep every number as written in `Phone.raw`.

**Consequences:** The user can fix area codes later in the contacts app or in Excel.
