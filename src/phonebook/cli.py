"""Run the book graph from the terminal.

uv run python -m phonebook.cli samples/              # real LLM calls (needs ANTHROPIC_API_KEY)
uv run python -m phonebook.cli samples/ --tier best  # find the layout with Opus
uv run python -m phonebook.cli samples/ --debug      # step tree + output/layout.debug.txt
"""

import argparse
import json
import uuid
from pathlib import Path

from langgraph.types import Command

from phonebook.book_graph import build_book_graph
from phonebook.debug import run_graph
from phonebook.llm import enable_disk_cache

PROFILE_FILE = Path(".cache/profile.json")


DEBUG_FILE = Path("output/layout.debug.txt")


def main(folder: str, tier: str | None = None, debug: bool = False) -> None:
    enable_disk_cache()  # same pages again -> saved answer, $0
    graph = build_book_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    if tier:
        config["configurable"]["tiers"] = {"discover_layout": tier}
    if debug:
        DEBUG_FILE.unlink(missing_ok=True)  # a new file for each run
    debug = DEBUG_FILE if debug else None

    result = run_graph(graph, {"book_id": folder}, config, debug)
    while "__interrupt__" in result:  # the graph paused and waits for us
        question = result["__interrupt__"][0].value
        print(json.dumps(question, ensure_ascii=False, indent=2))
        if input("Accept this layout? [y/n] ").strip().lower() == "y":
            answer = {"accept": True}
        else:
            path = input("Path to an edited profile JSON file: ").strip()
            with open(path, encoding="utf-8") as f:
                answer = {"profile": json.load(f)}
        result = run_graph(graph, Command(resume=answer), config, debug)

    PROFILE_FILE.parent.mkdir(exist_ok=True)
    PROFILE_FILE.write_text(result["profile"].model_dump_json(indent=2), encoding="utf-8")
    print(f"\nSaved the layout to {PROFILE_FILE} (cli_page uses it).")
    print(f"Cost: ${result.get('cost_usd', 0):.4f}")
    for d in result["decisions"]:
        model = f" [{d.model}, ${d.cost_usd:.4f}]" if d.model else ""
        print(f"- {d.node}: {d.choice} ({d.reason}){model}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find and confirm the layout of a phone book.")
    parser.add_argument("folder", nargs="?", default="samples")
    parser.add_argument(
        "--tier", choices=["cheap", "strong", "best"], help="model for discover_layout"
    )
    parser.add_argument(
        "--debug", action="store_true", help="show the graph steps; details go to a file"
    )
    args = parser.parse_args()
    main(args.folder, args.tier, args.debug)
