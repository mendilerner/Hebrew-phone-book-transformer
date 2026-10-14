"""Agent tools for read_page (docs/design/tools.md). The LLM decides when to call them.

A tool that returns an image puts it in the tool message, so the model can see it.
Tools are made per page (make_tools), because they need that page's image.
"""

from typing import Literal

from langchain_core.tools import BaseTool, tool
from PIL import Image

from phonebook.images import crop_block
from phonebook.phones import parse_phone
from phonebook.rows import RowLines, ink_crosses_line, with_row_numbers

PAD = {"strip": 0.35, "zoom": 0.5}  # extra space above and below a row, in row heights


def make_tools(img: Image.Image, rows: RowLines) -> list[BaseTool]:
    def no_rows() -> str | None:
        if rows.row_count:
            return None
        return "This page has no printed row lines. Use crop_region instead."

    @tool
    def row_view(row: int, mode: Literal["strip", "window3", "zoom"] = "strip") -> list | str:
        """See one row again, bigger. Rows are the red numbers on the page image.

        strip: the row with some space above and below.
        window3: the row above, this row (red bar on the left) and the row below.
                 Use it when ink crosses the row lines.
        zoom: the row in two bigger pictures, the right half and the left half.
              Use it for small or unclear letters and digits.
        """
        if error := no_rows():
            return error
        if not 1 <= row <= rows.row_count:
            return f"No row {row}. Rows are 1..{rows.row_count}."
        top, bottom = rows.row_box(row)
        height = bottom - top
        if mode == "window3":
            top = rows.row_box(max(1, row - 1))[0]
            bottom = rows.row_box(min(rows.row_count, row + 1))[1]
            marked = with_row_numbers(img, rows, mark=row)
            box = (0, top - height // 4, marked.width, bottom + height // 4)
            return [
                _text(f"rows {row - 1}-{row + 1}, row {row} has the red bar"),
                crop_block(marked, box),
            ]
        pad = round(height * PAD[mode])
        top, bottom = top - pad, bottom + pad
        if mode == "strip":
            return [_text(f"row {row}, strip"), crop_block(img, (0, top, img.width, bottom))]
        overlap = img.width // 10  # a word in the middle is in both halves
        half = img.width // 2
        return [
            _text(f"row {row}, zoom: right half"),
            crop_block(img, (half - overlap, top, img.width, bottom)),
            _text(f"row {row}, zoom: left half"),
            crop_block(img, (0, top, half + overlap, bottom)),
        ]

    @tool
    def crop_region(x0: float, y0: float, x1: float, y1: float, pad: float = 0.02) -> list | str:
        """See any part of the page in full resolution: a note, a crossed digit, a margin.

        x0, y0, x1, y1 are parts of the page from 0 to 1 (0,0 = top left), without
        the white strip with the row numbers. pad adds space around the box.
        """
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            return "Use 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1."
        box = (
            round((x0 - pad) * img.width),
            round((y0 - pad) * img.height),
            round((x1 + pad) * img.width),
            round((y1 + pad) * img.height),
        )
        return [_text(f"region {x0:.2f},{y0:.2f} - {x1:.2f},{y1:.2f}"), crop_block(img, box)]

    @tool("ink_crosses_line")
    def ink_crosses(row: int) -> dict | str:
        """Free check: does the handwriting of this row go over the line above or below?
        If yes, a strip cuts letters: use window3."""
        if error := no_rows():
            return error
        if not 1 <= row <= rows.row_count:
            return f"No row {row}. Rows are 1..{rows.row_count}."
        return ink_crosses_line(img, rows, row)

    @tool
    def check_phone(text: str) -> dict:
        """Free check of a phone number you read: its digits and kind (mobile, landline,
        short_code, or unknown = it looks wrong, for example a missing digit)."""
        return parse_phone(text).model_dump()

    return [row_view, crop_region, ink_crosses, check_phone]


def _text(text: str) -> dict:
    return {"type": "text", "text": text}
