# 0018: A bolder tie-breaker: "sure" when the ink clearly fits one reading

Date: 2026-11-04 · Status: Proposed (measured: the user decides) · Builds: 0015, 0016

**Decision:** in `TIE_PROMPT` only, rule 5 changes.
- Before: `sure` only if every letter and digit is clear. Never guess.
- Now: `sure` when the ink clearly fits the reading better than any other, even if
  the handwriting is not perfect. `sure = false` only when two readings still fit
  equally well. The prompt says that a second model (`verify`) checks every sure answer.
- The reader prompts don't change, so both reads come from the disk cache and the
  test is clean: only the tie-breaker (and so verify) changes.

**Why:** on the first real page the tie-breaker was sure about 0 of 13 doubts, so
`verify` never ran and every doubt went to the human, also the 6 that the
tie-breaker had right. The 0015 rule (two models must agree) still protects us:
a bold "sure" alone can't put a name in the contacts.

**Result** (same page, same two reads, `cli_score --stages`):

| | before | after |
|---|---|---|
| tie-breaker sure | 0 of 13 | 10 of 13 (6 right, 4 wrong) |
| verify yes | - | 3, all right |
| verify no | - | 7: 4 wrong (caught) + 3 right (too strict) |
| contacts / review | 4 / 13 | 6 / 11 |
| wrong names in contacts | 0 | 0 |
| names exact (final) | 10 of 17 | 10 of 17 (same answers, more of them trusted) |
| cost | $0.05 | $0.15 (verify now runs) |

The 3 rows where the tie-breaker was not sure were all wrong, so "not sure" is a
good signal. verify caught every wrong sure answer, but it also said no to half of
the right ones. One page and one run, so it is a first signal, not proof.
