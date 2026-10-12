# Graph topology (proposal, not accepted yet)

Legend: **R** = rule router, **L** = LLM router, **A** = ReAct agent,
⏸ = `interrupt` (human), ⇉ = `Send` (parallel fan-out).

## Book graph (parent)

```mermaid
flowchart TD
    S([START]) --> load_book
    load_book --> discover_layout
    discover_layout -->|R: unclear, tries left| discover_layout
    discover_layout -->|R: clear| confirm_layout["confirm_layout ⏸"]
    confirm_layout --> save_profile["save_profile (Store)"]
    save_profile -->|⇉ one Send per page| page_graph[["page_graph (sub-graph)"]]
    page_graph --> find_duplicates
    find_duplicates -->|L: sure| review_gate
    find_duplicates -->|L: not sure → review_queue| review_gate
    review_gate -->|R: queue empty| export
    review_gate -->|R: queue has items| human_review["human_review ⏸ (one batch)"]
    human_review --> export
    export --> E([END])
```

| Node | Does | LangGraph concept |
|---|---|---|
| `load_book` | lists page images, picks 2-3 sample pages | plain node |
| `discover_layout` | vision LLM builds `LayoutProfile` | structured output, self-loop with counter |
| `confirm_layout` | shows profile, user accepts or edits it | `interrupt` + `Command(resume=...)` |
| `save_profile` | saves profile per book | `Store` |
| (edge) | `Send("page_graph", {...})` per page | map-reduce |
| `page_graph` | see below | sub-graph as a node |
| `find_duplicates` | same person on 2 pages? | LLM router |
| `review_gate` / `human_review` | ask once for all doubtful entries | conditional edge + `interrupt` |
| `export` | Excel + `.vcf` | plain node |

## Page sub-graph

```mermaid
flowchart TD
    S([START]) --> classify_page
    classify_page -->|L: empty / cover| E([END])
    classify_page -->|L: different layout| rediscover_layout
    classify_page -->|L: entries| read_page
    rediscover_layout --> read_page
    read_page["read_page (A: agent + image tools)"] --> grade_entries
    grade_entries -->|R: all good| page_fix
    grade_entries -->|R: bad, tries left| choose_fix
    grade_entries -->|R: bad, no tries left → review_queue| page_fix
    choose_fix["choose_fix (L)"] -->|⇉ one Send per bad row| reread_row
    reread_row --> grade_entries
    page_fix -->|R: split entry / wrong letter order| choose_fix
    page_fix -->|R: ok| finalize_page
    finalize_page --> E
```

| Node | Does | LangGraph concept |
|---|---|---|
| `classify_page` | entries / empty / cover / different layout | LLM router |
| `rediscover_layout` | layout for this page only | reuses the discovery prompt |
| `read_page` | agent reads the whole page, uses tools when unsure | ReAct agent (its own small sub-graph) |
| `grade_entries` | rules + LLM check, sets `confidence` and `issues` | conditional edge on scores |
| `choose_fix` | picks a fix from the grader's reason (zoom, 3-row window, second model) | LLM router + nested `Send` |
| `reread_row` | reads one row with the chosen view | map-reduce inside a sub-graph |
| `page_fix` | merges entries split over 2 rows, checks letter order | rule router |
| `finalize_page` | writes `contacts`, `review_queue`, `decisions` | sub-graph output → parent reducers |

## Loop limits

- `discover_layout`: max 2 extra tries.
- `grade_entries` → `choose_fix` → `reread_row`: max `max_attempts` per row (default 3).
- `page_fix` → `choose_fix`: once per page.
