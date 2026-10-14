# 0010: Layout discovery loop

Date: 2026-10-14 · Status: Accepted

**Change:** the `discover_layout` self-loop is now two nodes:
`discover_layout` → (R) → `add_sample_page` → `discover_layout`.
- New state key `BookState.layout_clear` (bool): the LLM says if the layout is clear.
- `add_sample_page` adds the page furthest from the current samples.
- The counter is `len(sample_pages)` (starts at 2, max 2 extra), so no extra counter key.
- If the layout is still unclear after the tries, `confirm_layout` asks the human anyway.

**Why:** a node that only changes the input of the next try is easier to read and
test than a node that loops on itself.

**Also:** structured output uses `method="json_schema"`. LangChain's default
(forced tool call) is refused by the newest Claude models.
