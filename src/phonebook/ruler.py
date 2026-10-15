"""A ruler next to the page, so the agent can say WHERE to look (no LLM, free).

Decision 0014: finding the printed row lines with OpenCV failed on real photos
(it found 2-3 lines, and some false ones). A ruler does not find anything, so it
can't be wrong, and it is the same for every book.
"""

from PIL import Image, ImageDraw, ImageFont

STRIP = 0.06  # size of the ruler strips, as a part of the page width


def with_ruler(img: Image.Image) -> Image.Image:
    """The page with a ruler on the left (0 = top, 100 = bottom) and on the top
    (0 = left, 100 = right). Numbers are % of the page. Never drawn on the page."""
    strip = max(40, round(img.width * STRIP))
    pad = strip // 2  # room on the right and bottom for the "100" labels
    out = Image.new("RGB", (img.width + strip + pad, img.height + strip + pad), "white")
    out.paste(img, (strip, strip))
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=max(12, strip // 3))
    width = max(1, strip // 25)

    for pct in range(0, 101, 5):  # left ruler: height of the page
        y = strip + round(img.height * pct / 100)
        long = pct % 10 == 0
        draw.line(
            (strip - (strip // 3 if long else strip // 6), y, strip - 1, y), fill="red", width=width
        )
        if long:
            draw.text((2, y), str(pct), fill="red", font=font, anchor="lm")

    for pct in range(0, 101, 10):  # top ruler: width of the page
        x = strip + round(img.width * pct / 100)
        draw.line((x, strip - strip // 3, x, strip - width), fill="red", width=width)
        draw.text((x, 2), str(pct), fill="red", font=font, anchor="mt")
    return out
