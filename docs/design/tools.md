# Tool list

Three kinds of "tools". Only the first kind is a real LLM tool.

| Kind | Who calls it | Costs money? |
|---|---|---|
| **Agent tools** | the LLM, inside `read_page` (ReAct loop) | yes, each call is one more LLM turn |
| **Python helpers** | our nodes, directly | no |
| **LLM calls** | our nodes, one call with structured output | yes, one call |

## 1. Agent tools (`read_page` only, max 4 calls per page)

| Tool | Input | Returns | Why |
|---|---|---|---|
| `row_view` | `row`, `mode`: `strip` / `window3` / `zoom` | image(s) | the row views from [0003](../decisions/0003-flexible-row-reading.md); zoom = right half + left half |
| `crop_region` | box `x0, y0, x1, y1` (0..1 of the page), `pad` | image | free look at any part (a note, a crossed digit) |
| `ink_crosses_line` | `row` | `{above: bool, below: bool}` | tells the agent which view to pick; OpenCV, no LLM |
| `check_phone` | `text` | `Phone` (digits, kind) or error | the agent checks a number it read; same code as `parse_phone` |

- Image tools return an **image** in the tool message, so the model sees it.
- The page the agent sees first has the row numbers drawn in a white strip on the
  left, so its row numbers and ours are the same ([0013](../decisions/0013-agent-tools-first.md)).
- Image tools only cut the page file on disk; the state keeps only paths.
- The agent is the **prebuilt** `create_agent` (LangChain 1.x), with
  `ToolCallLimitMiddleware(run_limit=4)` (default `exit_behavior="continue"`: after
  4 calls tools are blocked, and the model must answer with what it has).
  Inside, it is the same 2-node graph (`model` ⇄ `tools`).
  `response_format=ProviderStrategy(PageRead)` returns the page read as structured output.

## 2. Python helpers (no LLM, free)

| Helper | Used in | Does |
|---|---|---|
| `list_pages` | `load_book` | finds page images, sorts them, picks 2-3 sample pages |
| `prepare_image` | `load_book` | fixes rotation, resizes to a max size (fewer image tokens) |
| `find_row_lines` | `read_page`, tools | finds printed row lines (OpenCV); returns nothing if the book has none |
| `parse_phone` | `grade_entries`, `export` | `raw` → digits + kind (mobile / landline / old 7-digit / `*` short code) |
| `rule_checks` | `grade_entries` | digit count, empty name, letter order → `issues` |
| `track_cost` | every LLM call | reads token usage → adds to `cost_usd` (a LangChain callback) |
| `llm_cache` | dev mode | saves LLM answers on disk; same input → saved answer, $0 |
| `profile_store` | `save_profile`, pages | get / put `LayoutProfile` in the LangGraph `Store` |
| `export_excel` | `export` | one row per contact, one column per phone (openpyxl) |
| `export_vcf` | `export` | one vCard per contact with a mobile number |

## 3. LLM calls (structured output, no tools)

| Node | Returns |
|---|---|
| `discover_layout` / `rediscover_layout` | `LayoutProfile` |
| `classify_page` | `page_kind` |
| `grade_entries` (only when rules can't decide) | `confidence` + `issues` |
| `choose_fix` | which view + which model for each bad row |
| `reread_row` | one `Contact` |
| `find_duplicates` | merge / keep both / ask |

All LLM nodes take their model from `config["configurable"]` ([0007](../decisions/0007-cost-control.md)).
