"""See which row lines OpenCV finds on a page. Free: no LLM call.

uv run python -m phonebook.cli_rows samples/p05.jpg

Saves output/<page>.rows.jpg: the page with a blue line on every line found and
the red row numbers the read_page agent will see. Check it before paying for a read.
"""

import argparse
from pathlib import Path

from PIL import ImageDraw

from phonebook.images import load_page
from phonebook.rows import find_row_lines, with_row_numbers

OUTPUT_DIR = Path("output")


def preview(image_path: str) -> tuple[Path, int]:
    img = load_page(image_path)
    rows = find_row_lines(img)
    shown = with_row_numbers(img, rows) if rows.row_count else img.copy()
    margin = shown.width - img.width  # the white strip on the left
    draw = ImageDraw.Draw(shown)
    for y in rows.ys:
        draw.line((margin, y, shown.width, y), fill="blue", width=max(2, img.height // 600))
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"{Path(image_path).stem}.rows.jpg"
    shown.save(path, quality=85)
    return path, rows.row_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image")
    args = parser.parse_args()
    path, count = preview(args.image)
    if count:
        print(f"Found {count + 1} lines = {count} rows. Saved: {path}")
    else:
        print(f"No printed row lines found (the agent will count rows itself). Saved: {path}")


if __name__ == "__main__":
    main()
