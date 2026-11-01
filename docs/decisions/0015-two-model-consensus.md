# 0015: Two-model consensus instead of the agent with tools

Date: 2026-11-01 · Status: Accepted · Supersedes: 0013 (agent tools), 0014 (ruler and
tools), the retry loop in 0005 (decision points 4-5) and point 1 of 0007 ("one read
per page")

**Context:**
- The `read_page` agent with tools (zoom, crop, ruler) helped very little in the
  user's tests (tool check levels 1 and 2).
- A manual test (one page, 16 rows, one prompt, three models) showed:
  - Claude (Opus) and GPT agree on all phones except one. Gemini Flash-Lite gets the
    phones right but the names badly wrong.
  - After small cleanup, Claude and GPT agree on 7 of 16 names. **All 7 were right.**
  - In 7 of the 9 other rows, one of the two was right. In 2 rows both were wrong,
    and in both of those rows they disagreed.
- So agreement between two strong models is a good signal, and a disagreement shows
  exactly where to look.
- The user does not trust crops: if a crop misses part of a row, nobody notices.

**Decision:**
1. **Read the page with two models in parallel:** Claude and GPT, the same prompt
   (based on the user's manual-test prompt and the layout profile). Gemini is an
   optional third reader for **phones only** (setting, off by default: on the free
   tier Google may use the data, so use a paid key for real pages).
2. **Compare in Python (free):**
   - Normalize: phones = digits and `*` only; names = no `'`, `"`, `-`, single
     spaces.
   - Match rows by an agreed phone number, not by row number. Rows with no shared
     phone are matched by name similarity and position, or go to doubts.
   - Phones: Claude and GPT agree → OK. With Gemini on: a majority of 3.
   - Names: Claude and GPT must agree exactly (after normalizing).
   - Both agree → `contacts`, `source = "agreed"`. Otherwise → the row is a doubt.
3. **Tie-break (Claude, one call per page):** the **full page** again (no crops) and
   all doubtful rows, each pointed at by its phone number ("the row with phone
   0501234567"). The two readings are labeled A and B in random order, not
   "yours" and "GPT's", so Claude can't favor its own reading. For each row it
   answers: A, B, a new reading, or "can't tell", plus `sure` (yes/no).
4. **Verify (GPT, one call per page):** for each row where the tie-breaker was sure:
   the full page and a yes/no question, "Is the name in the row with phone X
   written as Y?". Yes → `contacts`, `source = "tie-breaker"`. No → review.
   This keeps the rule "two models agree" without a human.
5. **Human review:** "can't tell", "not sure" and "verify said no" go to
   `review_queue` with every reading, so the human picks or fixes one.
6. The Excel gets a `source` column (agreed / tie-breaker / human), so the user can
   spot-check the tie-breaker's names later.

**Removed:** the agent and its tools, the ruler, `check_before_answer`, crops
(`crop_block`). The ReAct concept was learned in step 6; this flow teaches
parallel branches with a reducer, rule routers and several LLM providers instead.
The code is removed in the build PR, not in this design PR.

**Why:** the user's goal is the fewest names for human review, with no wrong name
in the Excel. Two strong models that agree were right every time in the test. A
second model checks every automatic tie-break, so a wrong "sure" from one model
alone can't reach the Excel.

**Consequences:**
- Cost per page: 2 reads + up to 2 small calls (only when there are doubts), about
  4 calls instead of 1-5. The $10 per book budget stays.
- New API keys on the user's computer only (`.env`, gitignored):
  `OPENAI_API_KEY`, and `GOOGLE_API_KEY` if Gemini is on. A ChatGPT or Claude
  subscription does not include API calls.
- New packages: `langchain-openai` (and `langchain-google-genai` for Gemini).
- One page is a small sample. After the build, measure on hand-checked pages
  (`cli_score`): are agreed names ever wrong? Is the verify step needed?
