"""Score page reads against a page you checked by hand. Free: no LLM.

1. Make an answer key from a run, then fix it by hand (it has real numbers, so it
   lives in truth/, which is gitignored):
     uv run python -m phonebook.cli_score --make-truth output/p05.strong.json truth/p05.json
2. Compare one or more runs with it, for example with and without a tool:
     uv run python -m phonebook.cli_score truth/p05.json output/p05.strong.*.json

For each run: names exactly right, letters right in names, phones exactly right,
missing and extra entries, and cost. Entries are matched by name and phone, not by
row number (rows can differ between runs).
"""

import argparse
import json
from difflib import SequenceMatcher
from pathlib import Path


def _entries(run: dict) -> list[dict]:
    return run.get("contacts", []) + run.get("review_queue", [])


def _digits(phone) -> str:
    raw = phone["raw"] if isinstance(phone, dict) else phone
    return "".join(ch for ch in raw if ch.isdigit() or ch in "*?")


def make_truth(run_path: Path, truth_path: Path) -> None:
    run = json.loads(run_path.read_text(encoding="utf-8"))
    entries = sorted(_entries(run), key=lambda e: e["rows"])
    truth = [
        {"rows": e["rows"], "name": e["name"], "phones": [p["raw"] for p in e["phones"]]}
        for e in entries
    ]
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    truth_path.write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _match(want: dict, got: dict) -> float:
    """How well a read entry fits a true entry: name likeness (0-1) + 1 if a phone is the same."""
    want_phones = {_digits(p) for p in want["phones"]}
    same_phone = bool(want_phones & {_digits(p) for p in got["phones"]})
    return _similar(want["name"], got["name"]) + same_phone


def score(truth: list[dict], run: dict) -> dict:
    found = _entries(run)
    used: set[int] = set()
    names_exact = letters = phones_exact = phones_total = 0
    missing = 0
    for want in truth:
        want_phones = {_digits(p) for p in want["phones"]}

        free = [i for i in range(len(found)) if i not in used]
        best = max(free, key=lambda i: _match(want, found[i]), default=None)
        if best is None or _match(want, found[best]) < 0.5:
            missing += 1
            phones_total += len(want_phones)
            continue
        used.add(best)
        got = found[best]
        names_exact += want["name"] == got["name"]
        letters += _similar(want["name"], got["name"])
        got_phones = {_digits(p) for p in got["phones"]}
        phones_exact += len(want_phones & got_phones)
        phones_total += len(want_phones)
    n = len(truth) or 1
    return {
        "names exact": f"{names_exact}/{len(truth)}",
        "name letters": f"{100 * letters / n:.0f}%",
        "phones exact": f"{phones_exact}/{phones_total}",
        "missing": missing,
        "extra": len(found) - len(used),
        "cost": f"${run.get('cost_usd', 0):.4f}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--make-truth", nargs=2, metavar=("RUN_JSON", "TRUTH_JSON"))
    parser.add_argument("truth", nargs="?")
    parser.add_argument("runs", nargs="*")
    args = parser.parse_args()
    if args.make_truth:
        make_truth(Path(args.make_truth[0]), Path(args.make_truth[1]))
        print(f"Saved {args.make_truth[1]}. Now fix every name and phone in it by hand.")
        return
    truth = json.loads(Path(args.truth).read_text(encoding="utf-8"))
    for run_path in args.runs:
        result = score(truth, json.loads(Path(run_path).read_text(encoding="utf-8")))
        print(f"{run_path}\n  " + " | ".join(f"{k}: {v}" for k, v in result.items()))


if __name__ == "__main__":
    main()
