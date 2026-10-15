"""Read ONE page with the page sub-graph, using the layout saved by phonebook.cli.

uv run python -m phonebook.cli samples/                           # first: find the layout
uv run python -m phonebook.cli_page samples/p05.jpg               # then: read one page
uv run python -m phonebook.cli_page samples/p05.jpg --tier best   # same page with Opus
uv run python -m phonebook.cli_page samples/p05.jpg --debug       # step tree + details file
uv run python -m phonebook.cli_page samples/p05.jpg --tools none  # no agent tools (compare!)

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


def run_page(
    image_path: str,
    tier: str | None = None,
    debug: Path | None = None,
    tools: list[str] | None = None,
) -> dict:
    """Run the page graph. `tier` (cheap/strong/best) sets the model for every LLM node."""
    configurable = {}
    if tier:
        configurable["tiers"] = {node: tier for node in LLM_NODES}
    if tools is not None:
        configurable["agent_tools"] = tools
    config = {"configurable": configurable}
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
        "tools": _tools_label(setting(config, "agent_tools")),
        "cost_usd": round(out.get("cost_usd", 0), 6),
        "page_kind": out.get("page_kind"),
        "skeleton": out.get("skeleton", []),
        "contacts": [c.model_dump(mode="json") for c in out.get("contacts", [])],
        "review_queue": [c.model_dump(mode="json") for c in out.get("review_queue", [])],
        "decisions": [d.model_dump(mode="json") for d in out.get("decisions", [])],
    }


def run_name(image_path: str, tier: str | None, tools: list[str] | None) -> str:
    """For example p05.strong (all tools), p05.strong.no-tools, p05.strong.zoom_band."""
    name = f"{Path(image_path).stem}.{tier or 'default'}"
    if tools is not None:
        name += "." + ("+".join(tools) or "no-tools")
    return name


def _tools_label(tools: list[str] | None) -> list[str] | str:
    """None means all tools; an empty list means no tools (not the same!)."""
    if tools is None:
        return "all"
    return tools or "none"


def save_json(result: dict, name: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"{name}.json"
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
    parser.add_argument(
        "--tools",
        help="agent tools to turn on, comma separated (zoom_band,crop_region,check_phone) "
        "or 'none'. Default: all",
    )
    parser.add_argument(
        "--debug", action="store_true", help="show the graph steps; details go to a file"
    )
    args = parser.parse_args()

    enable_disk_cache()  # same page + same model + same prompt -> saved answer, $0
    tools = None
    if args.tools:
        tools = [] if args.tools == "none" else args.tools.split(",")
    name = run_name(args.image, args.tier, tools)
    debug_file = None
    if args.debug:
        debug_file = OUTPUT_DIR / f"{name}.debug.txt"
        debug_file.unlink(missing_ok=True)  # a new file for each run
    result = run_page(args.image, args.tier, debug_file, tools)
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
    print(f"Saved: {save_json(result, name)}")


if __name__ == "__main__":
    main()
