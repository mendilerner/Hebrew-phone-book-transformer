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
- Try 1 (decision 0017, draft PR #17): readers copy letters. Mixed: final 10 → 9.
- Try 2 (decision 0018, proposed): bolder tie-breaker. Sure 0 → 10 of 13, verify
  yes 3 (all right), no 7 (4 wrong caught, 3 right refused). Contacts 4 → 6, review
  13 → 11, still 0 wrong names in contacts. Cost $0.05 → $0.15.
- Fixed: the disk cache could not load GPT answers (the parsed object), so a GPT
  read was never free again.

Open question for the user: should `.vcf` include landline and `*` numbers (now: yes)?
