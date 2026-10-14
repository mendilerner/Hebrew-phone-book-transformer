"""Run the book graph from the terminal.

uv run python -m phonebook.cli samples/          # real LLM calls (needs ANTHROPIC_API_KEY)
"""

import json
import sys
import uuid
from pathlib import Path

from langgraph.types import Command

from phonebook.book_graph import build_book_graph
from phonebook.llm import enable_disk_cache

PROFILE_FILE = Path(".cache/profile.json")


def main(folder: str) -> None:
    enable_disk_cache()  # same pages again -> saved answer, $0
    graph = build_book_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = graph.invoke({"book_id": folder}, config)
    while "__interrupt__" in result:  # the graph paused and waits for us
        question = result["__interrupt__"][0].value
        print(json.dumps(question, ensure_ascii=False, indent=2))
        if input("Accept this layout? [y/n] ").strip().lower() == "y":
            answer = {"accept": True}
        else:
            path = input("Path to an edited profile JSON file: ").strip()
            with open(path, encoding="utf-8") as f:
                answer = {"profile": json.load(f)}
        result = graph.invoke(Command(resume=answer), config)

    PROFILE_FILE.parent.mkdir(exist_ok=True)
    PROFILE_FILE.write_text(result["profile"].model_dump_json(indent=2), encoding="utf-8")
    print(f"\nSaved the layout to {PROFILE_FILE} (cli_page uses it).")
    print(f"Cost: ${result.get('cost_usd', 0):.4f}")
    for d in result["decisions"]:
        print(f"- {d.node}: {d.choice} ({d.reason})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "samples")
