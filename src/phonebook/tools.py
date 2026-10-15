"""Agent tools for read_page (docs/design/tools.md). The LLM decides when to call them.

A tool that returns an image puts it in the tool message, so the model can see it.
Tools are made per page (make_tools), because they need that page's image.
Places are given in % of the page (0-100), the numbers on the ruler (decision 0014).
"""

from langchain_core.tools import BaseTool, tool
from PIL import Image

from phonebook.images import crop_block
from phonebook.phones import parse_phone

PAD = 1.5  # % of the page height added above and below a band


def make_tools(img: Image.Image, names: list[str] | None = None) -> list[BaseTool]:
    """The tools for this page. `names`: only these (None = all), to test each tool."""

    def px_y(pct: float) -> int:
        return round(img.height * pct / 100)

    def px_x(pct: float) -> int:
        return round(img.width * pct / 100)

    @tool
    def zoom_band(top: float, bottom: float) -> list | str:
        """See a band of the page across its full width, in full resolution and bigger:
        the right half and the left half as two pictures.

        top, bottom: the left ruler numbers (0 = top of the page, 100 = bottom).
        For one row use its top and bottom line; for ink that crosses a line,
        take a taller band (for example the row above and below too).
        """
        if not 0 <= top < bottom <= 100:
            return "Use 0 <= top < bottom <= 100 (numbers of the left ruler)."
        y0, y1 = px_y(top - PAD), px_y(bottom + PAD)
        overlap = img.width // 10  # a word in the middle is in both halves
        half = img.width // 2
        return [
            _text(f"band {top:g}-{bottom:g}: right half"),
            crop_block(img, (half - overlap, y0, img.width, y1)),
            _text(f"band {top:g}-{bottom:g}: left half"),
            crop_block(img, (0, y0, half + overlap, y1)),
        ]

    @tool
    def crop_region(x0: float, y0: float, x1: float, y1: float) -> list | str:
        """See any part of the page in full resolution: a note, a crossed digit, a margin.

        x0, x1: the top ruler numbers (0 = left edge, 100 = right edge).
        y0, y1: the left ruler numbers (0 = top, 100 = bottom).
        """
        if not (0 <= x0 < x1 <= 100 and 0 <= y0 < y1 <= 100):
            return "Use 0 <= x0 < x1 <= 100 and 0 <= y0 < y1 <= 100 (ruler numbers)."
        box = (px_x(x0 - 1), px_y(y0 - 1), px_x(x1 + 1), px_y(y1 + 1))
        return [_text(f"region x {x0:g}-{x1:g}, y {y0:g}-{y1:g}"), crop_block(img, box)]

    @tool
    def check_phone(text: str) -> dict:
        """Free check of a phone number you read: its digits and kind (mobile, landline,
        short_code, or unknown = it looks wrong, for example a missing digit)."""
        return parse_phone(text).model_dump()

    tools = [zoom_band, crop_region, check_phone]
    if names is None:
        return tools
    unknown = set(names) - {t.name for t in tools}
    if unknown:
        raise ValueError(f"Unknown tools: {sorted(unknown)}")
    return [t for t in tools if t.name in names]


def _text(text: str) -> dict:
    return {"type": "text", "text": text}
