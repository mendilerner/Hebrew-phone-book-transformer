# 0004: Generic design with a learned LayoutProfile

Date: 2026-10-01 · Status: Accepted

**Context:** The project must work for other Hebrew phone books too
(more columns, other layouts), not only the first book.

**Decision:** Learn the layout once per book from 2-3 sample pages into a
`LayoutProfile` (columns and their meaning, direction, printed rows, letter order,
quirks). A human confirms it (interrupt), and it is saved in the LangGraph Store.
Each page is checked against the profile; a different page gets its own layout.
The output is a fixed `Contact` format; unknown columns go to `Contact.extra`.

**Consequences:** A new book changes data, not code. Adds parent graph,
sub-graphs, interrupt with editing, Store, and nested Send.
