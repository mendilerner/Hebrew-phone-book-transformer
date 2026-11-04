# 0017: Readers copy letters, they don't "fix" names to common names

Date: 2026-11-04 · Status: Proposed (measured, mixed result: the user decides) · Builds: 0015

**Decision:** in `READ_PROMPT` (both readers), rule 3 changes.
- Before: read the letter shapes, then prefer a common Hebrew name when the ink allows it.
- Now: copy the letters you see. Don't change a name to a common name or word, even
  if it is one letter away. A family name often repeats on nearby rows: compare there.
- The tie-breaker and verify prompts don't change (one change at a time).

**Why:** the first real page scored with `cli_score --stages`: Claude read a rare
family name (ending in ק) as a very common name (ending in ך) in all 4 rows where
it appears; GPT read it right. Many of the 13 doubts were 1-letter "fixes" like
this. The old rule asked for exactly this mistake.

**Result** (same page, one run each, names exact of 17):

| stage | before | after |
|---|---|---|
| claude | 6 | 10 |
| gpt | 8 | 6 |
| tie-breaker / final | 10 | 9 |

Claude fixed the rare family name in all 4 rows. But both readers now misread
2 common names that they read right before (one letter each), so 2 agreed rows
became doubts. The final result did not get better. One run per prompt, so part
of the change may be chance.
