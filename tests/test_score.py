"""cli_score: compare page reads with a hand-checked page. Free, made-up numbers."""

import json

from phonebook import cli_score


def run(entries, cost=0.01):
    return {"contacts": entries, "review_queue": [], "cost_usd": cost}


def entry(name, *phones, rows=(1,)):
    return {"rows": list(rows), "name": name, "phones": [{"raw": p} for p in phones]}


def test_score_counts_right_and_wrong(tmp_path):
    truth = [
        {"rows": [1], "name": "כהן משה", "phones": ["050-1234567"]},
        {"rows": [2], "name": "לוי דוד", "phones": ["03-1234567"]},
        {"rows": [3], "name": "פרץ", "phones": ["6123456"]},
    ]
    got = run(
        [
            entry("כהן משה", "050-1234567"),
            entry("לוי דור", "03-1234561", rows=(2,)),  # one letter, one digit wrong
            entry("שטויות", "1", rows=(9,)),  # not on the page
        ]
    )
    result = cli_score.score(truth, got)
    assert result["names exact"] == "1/3"
    assert result["phones exact"] == "1/3"
    assert result["missing"] == 1 and result["extra"] == 1

    run_file = tmp_path / "run.json"
    run_file.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    cli_score.make_truth(run_file, tmp_path / "truth" / "p.json")
    made = json.loads((tmp_path / "truth" / "p.json").read_text(encoding="utf-8"))
    assert made[0] == {"rows": [1], "name": "כהן משה", "phones": ["050-1234567"]}
