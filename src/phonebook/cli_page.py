"""Read ONE page with the page sub-graph, using the layout saved by phonebook.cli.

uv run python -m phonebook.cli samples/              # first: find and confirm the layout
uv run python -m phonebook.cli_page samples/p05.jpg  # then: read one page
"""

import sys

from phonebook.cli import PROFILE_FILE
from phonebook.llm import enable_disk_cache, setting
from phonebook.page_graph import build_page_graph
from phonebook.schema import LayoutProfile


def main(image_path: str) -> None:
    enable_disk_cache()
    profile = LayoutProfile.model_validate_json(PROFILE_FILE.read_text(encoding="utf-8"))
    out = build_page_graph().invoke(
        {
            "page_no": 1,
            "image_path": image_path,
            "profile": profile,
            "max_attempts": setting(None, "max_attempts"),
        }
    )
    for title, key in (("Good", "contacts"), ("To review", "review_queue")):
        print(f"\n{title}:")
        for c in out.get(key, []):
            phones = ", ".join(p.raw for p in c.phones)
            issues = f"  <- {'; '.join(c.issues)}" if c.issues else ""
            print(f"  rows {c.rows}: {c.name} | {phones} ({c.confidence:.2f}){issues}")
    print(f"\nCost: ${out.get('cost_usd', 0):.4f}")


if __name__ == "__main__":
    main(sys.argv[1])
