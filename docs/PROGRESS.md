# Progress

Project memory is off, so progress lives here. Update it in each PR.

Design: 1 main flow ✓ · 2 decision points ✓ · 3 state ✓ · 4 topology + cost ✓ ·
5 tools ✓ · 6 MVP scope ✓ (decisions 0001-0009).

Build order (decision 0009):
1. ✓ Project setup
2. ✓ Free helpers (phones, rule checks, export)
3. ✓ `discover_layout` + `confirm_layout`
4. ✓ Simple page sub-graph
5. ○ Book graph: `Send` + reducers (next)
6. ✓ Agent tools + 4-call limit (done before 5, decision 0013)
7. ○ Retry loop: grade → `choose_fix` → `reread_row`, model ladder, budget
8. ○ `page_fix`
9. ○ Human review + export, full-book run, real cost

Open question for the user: should `.vcf` include landline and `*` numbers (now: yes)?
