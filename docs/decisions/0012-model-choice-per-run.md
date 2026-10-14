# 0012: Pick the model per run, log it in each decision

Date: 2026-10-14 · Status: Accepted

**Context:** the first real page run gave weak results. To compare models we need
to switch the model easily and see which model gave which answer.

**Decision:**
- A third ladder step: `best` = Opus 5.5. No node uses it by default; a run picks it.
- `Decision` gets two optional fields: `model` and `cost_usd` (None / 0 for rules
  and humans). `read_page` now logs a decision too.
- `cli` and `cli_page` get `--tier cheap|strong|best`.
- `cli_page` saves the full result (models, cost, skeleton, contacts, review queue,
  decisions) as readable JSON in `output/` (gitignored: real numbers).

**Why:** model choice must come from measuring real pages (decision 0007). This
makes the measurement cheap to run and easy to read.
