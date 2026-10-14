"""Find the printed row lines on a page with OpenCV (no LLM, free).

Decision 0003: we never cut the page blindly. These helpers only tell the
agent WHERE the rows are, so its tools can show one row in a good view.
"""

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class RowLines:
    """y position (pixels) of each printed line, top to bottom. Row k is between line k-1 and k."""

    ys: list[int]
    height: int
    width: int

    @property
    def row_count(self) -> int:
        return max(0, len(self.ys) - 1)

    def row_box(self, row: int) -> tuple[int, int]:
        """(top, bottom) in pixels of row `row` (1 = the first row)."""
        if not 1 <= row <= self.row_count:
            raise ValueError(f"row must be 1..{self.row_count}")
        return self.ys[row - 1], self.ys[row]


def _masks(img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    """(all ink, only long horizontal lines) as 0/255 images."""
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    ink = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15
    )
    # An "open" with a wide, flat kernel keeps only long horizontal strokes: the printed lines.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, img.width // 15), 1))
    lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
    return ink, lines


def find_row_lines(img: Image.Image) -> RowLines:
    """Printed row lines. Returns no lines if the book has none (the agent then uses crops)."""
    _, lines = _masks(img)
    # Pieces of one line (a photo is never quite straight) are grouped by their y.
    contours, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pieces = []
    for contour in contours:
        _, y, w, h = cv2.boundingRect(contour)
        pieces.append((y + h // 2, w))
    pieces.sort()

    gap = max(3, img.height // 150)  # pieces closer than this are the same line
    groups: list[list[tuple[int, int]]] = []
    for y, w in pieces:
        if groups and y - groups[-1][-1][0] <= gap:
            groups[-1].append((y, w))
        else:
            groups.append([(y, w)])
    ys = [
        round(sum(y * w for y, w in g) / sum(w for _, w in g))
        for g in groups
        if sum(w for _, w in g) >= 0.4 * img.width  # a real line goes across most of the page
    ]
    return RowLines(ys=ys, height=img.height, width=img.width)


def ink_crosses_line(img: Image.Image, rows: RowLines, row: int) -> dict[str, bool]:
    """Does handwriting go over the line above / below this row? Then a strip would cut it."""
    ink, lines = _masks(img)
    writing = cv2.subtract(ink, cv2.dilate(lines, np.ones((5, 5), np.uint8)))
    band = max(2, img.height // 300)
    top, bottom = rows.row_box(row)

    def crosses(y: int) -> bool:
        part = writing[max(0, y - band) : y + band + 1]
        return int(np.count_nonzero(part)) > 0.003 * part.size

    return {"above": crosses(top), "below": crosses(bottom)}


MARGIN = 0.06  # part of the width added on the left for the row numbers


def with_row_numbers(img: Image.Image, rows: RowLines, mark: int | None = None) -> Image.Image:
    """The page with a white strip on the left that shows the row numbers.

    The numbers are drawn next to the page, never on the handwriting. `mark`
    draws a red bar next to one row (used by the 3-row view).
    """
    margin = max(40, round(img.width * MARGIN))
    out = Image.new("RGB", (img.width + margin, img.height), "white")
    out.paste(img, (margin, 0))
    draw = ImageDraw.Draw(out)
    size = max(12, min(margin // 2, (rows.ys[1] - rows.ys[0]) * 2 // 3 if rows.row_count else 20))
    font = ImageFont.load_default(size=size)
    for row in range(1, rows.row_count + 1):
        top, bottom = rows.row_box(row)
        if row == mark:
            draw.rectangle((0, top, margin // 5, bottom), fill="red")
        draw.text((margin // 4, (top + bottom) // 2), str(row), fill="red", font=font, anchor="lm")
    return out
