"""Read ONE page with the page sub-graph, using the layout saved by phonebook.cli.

uv run python -m phonebook.cli samples/                           # first: find the layout
uv run python -m phonebook.cli_page samples/p05.jpg               # then: read one page
uv run python -m phonebook.cli_page samples/p05.jpg --tier best   # same page with Opus
uv run python -m phonebook.cli_page samples/p05.jpg --debug       # show LLM messages and steps

The full result is saved as JSON in output/ (gitignored: it has real numbers).
"""

import argparse
import json
from pathlib import Path

from phonebook.cli import PROFILE_FILE
from phonebook.debug import run_graph
from phonebook.llm import enable_disk_cache, model_name, setting
from phonebook.page_graph import build_page_graph
from phonebook.schema import LayoutProfile

LLM_NODES = ("classify_page", "read_page")
OUTPUT_DIR = Path("output")


def run_page(image_path: str, tier: str | None = None, debug: bool = False) -> dict:
    """Run the page graph. `tier` (cheap/strong/best) sets the model for every LLM node."""
    config = {"configurable": {"tiers": {node: tier for node in LLM_NODES}}} if tier else {}
    profile = LayoutProfile.model_validate_json(PROFILE_FILE.read_text(encoding="utf-8"))
    out = run_graph(
        build_page_graph(),
        {
            "page_no": 1,
            "image_path": image_path,
            "profile": profile,
            "max_attempts": setting(config, "max_attempts"),
        },
        config,
        debug,
    )
    return {
        "image": image_path,
        "models": {node: model_name(node, config) for node in LLM_NODES},
        "cost_usd": round(out.get("cost_usd", 0), 6),
        "page_kind": out.get("page_kind"),
        "skeleton": out.get("skeleton", []),
        "contacts": [c.model_dump(mode="json") for c in out.get("contacts", [])],
        "review_queue": [c.model_dump(mode="json") for c in out.get("review_queue", [])],
        "decisions": [d.model_dump(mode="json") for d in out.get("decisions", [])],
    }


def save_json(result: dict, image_path: str, tier: str | None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"{Path(image_path).stem}.{tier or 'default'}.json"
    # ensure_ascii=False keeps Hebrew readable (not \\u05e9...)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("image")
    parser.add_argument(
        "--tier",
        choices=sorted(setting(None, "models")),
        help="model for all LLM nodes: cheap=Haiku, strong=Sonnet, best=Opus",
    )
    parser.add_argument("--debug", action="store_true", help="print LLM messages and graph steps")
    args = parser.parse_args()

    enable_disk_cache()  # same page + same model + same prompt -> saved answer, $0
    result = run_page(args.image, args.tier, args.debug)
    for title, key in (("Good", "contacts"), ("To review", "review_queue")):
        print(f"\n{title}:")
        for c in result[key]:
            phones = ", ".join(p["raw"] for p in c["phones"])
            issues = f"  <- {'; '.join(c['issues'])}" if c["issues"] else ""
            print(f"  rows {c['rows']}: {c['name']} | {phones} ({c['confidence']:.2f}){issues}")
    print("\nModels:")
    for d in result["decisions"]:
        if d["model"]:
            print(f"  {d['node']}: {d['model']} (${d['cost_usd']:.4f})")
    print(f"Cost: ${result['cost_usd']:.4f}")
    print(f"Saved: {save_json(result, args.image, args.tier)}")


if __name__ == "__main__":
    main()
