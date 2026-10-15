"""Run ONE agent tool by hand and see exactly what the model would see. Free: no LLM.

uv run python -m phonebook.cli_tool samples/p05.jpg ruler                  # the page + ruler
uv run python -m phonebook.cli_tool samples/p05.jpg zoom_band 30 36        # one band
uv run python -m phonebook.cli_tool samples/p05.jpg crop_region 0 30 50 36 # one box
uv run python -m phonebook.cli_tool samples/p05.jpg check_phone 050-1234567

Images are saved in output/tool/ (gitignored).
"""

import argparse
import base64
import json
from pathlib import Path

from phonebook.images import load_page, to_block
from phonebook.ruler import with_ruler
from phonebook.tools import make_tools

OUTPUT_DIR = Path("output/tool")
ARGS = {
    "zoom_band": ["top", "bottom"],
    "crop_region": ["x0", "y0", "x1", "y1"],
    "check_phone": ["text"],
}


def save_block(block: dict, path: Path) -> Path:
    path.write_bytes(base64.b64decode(block["base64"]))
    return path


def run_tool(image_path: str, name: str, values: list[str]) -> list[str]:
    """Run the tool; return lines to print (texts and saved image paths)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem
    img = load_page(image_path)
    if name == "ruler":
        path = save_block(to_block(with_ruler(img)), OUTPUT_DIR / f"{stem}.ruler.jpg")
        return [f"saved {path}  (what read_page sends first)"]

    keys = ARGS[name]
    if len(values) != len(keys):
        raise SystemExit(f"{name} needs: {' '.join(keys)}")
    args = {k: (v if k == "text" else float(v)) for k, v in zip(keys, values, strict=True)}
    (tool,) = make_tools(img, [name])
    result = tool.invoke(args)
    if not isinstance(result, list):
        return [json.dumps(result, ensure_ascii=False)]
    lines, n = [], 0
    for block in result:
        if block["type"] == "text":
            lines.append(block["text"])
        else:
            n += 1
            tag = "-".join(f"{v:g}" for v in args.values())
            lines.append(
                f"  saved {save_block(block, OUTPUT_DIR / f'{stem}.{name}.{tag}.{n}.jpg')}"
            )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image")
    parser.add_argument("tool", choices=["ruler", *ARGS])
    parser.add_argument("values", nargs="*")
    args = parser.parse_args()
    for line in run_tool(args.image, args.tool, args.values):
        print(line)


if __name__ == "__main__":
    main()
