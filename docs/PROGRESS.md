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
6. ✗ Agent tools + 4-call limit (tried, not merged: it helped very little; replaced by 0015)
7. ✓ Two-model consensus: Claude + GPT read, compare, `tie_break`, `verify`
   (decisions 0015, 0016; replaces the retry loop and the agent tools)
8. ○ `page_fix`
9. ○ Human review + export, full-book run, real cost

Measuring: `cli_score --stages` scores each stage of one run (claude, gpt,
tie-breaker, final) and the verify check, against a hand-checked page in `truth/`.
First real page (18 rows, 17 entries, about $0.27): names exact claude 6, gpt 8,
tie-breaker 10, final 10 of 17; phones 23 of 23 in the final. verify did not run
(the tie-breaker was sure about 0 of 13 doubts). Next: improve the name reading
(prompt rule against "fixing" names, page context, word-by-word merge), one
change at a time, each measured with `--stages`.

Open question for the user: should `.vcf` include landline and `*` numbers (now: yes)?
