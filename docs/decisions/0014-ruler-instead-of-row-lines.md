# 0014: A ruler instead of finding row lines

Date: 2026-10-15 · Status: Accepted · Supersedes: row lines and `row_view` in 0013,
the "ink crosses this line?" check in 0003

**Context:** `find_row_lines` (OpenCV) was tested on real photos. At best it found
2-3 lines, and it added false lines. Wrong row numbers are worse than none.

**Decision:**
- No line detection, no OpenCV. The page the agent sees gets a red **ruler** on the
  left (0 = top, 100 = bottom) and on the top (0 = left, 100 = right), in % of the
  page, drawn next to the page, never on it. A ruler finds nothing, so it can't be
  wrong, and it is the same for every book.
- The agent counts rows itself (it did this well in the first real run).
- Tools: `zoom_band(top, bottom)` (a band across the page, as right half + left
  half, bigger), `crop_region(x0, y0, x1, y1)`, `check_phone(text)`.
  `row_view` and `ink_crosses_line` are removed: a taller band covers ink that
  crosses a line.

**Later (step 7):** `reread_row` needs to know where a row is. The agent can give
each entry's band on the ruler then.
