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


def test_make_truth_uses_the_true_name(tmp_path):
    marked = entry("לוי דור", "03-1234567")
    marked["the_true_name"] = "לוי דוד"
    run_file = tmp_path / "run.json"
    run_file.write_text(json.dumps(run([marked]), ensure_ascii=False), encoding="utf-8")
    cli_score.make_truth(run_file, tmp_path / "t.json")
    made = json.loads((tmp_path / "t.json").read_text(encoding="utf-8"))
    assert made[0]["name"] == "לוי דוד"


def test_stages_score_each_reader_and_verify():
    truth = [
        {"rows": [1], "name": "כהן משה", "phones": ["050-1234567"]},
        {"rows": [2], "name": "לוי דוד", "phones": ["03-1234567"]},
        {"rows": [3], "name": "פרץ רות", "phones": ["6123456"]},
    ]
    agreed = entry("כהן משה", "050-1234567")
    agreed["readings"] = {"claude": "כהן משה | 050-1234567", "gpt": "כהן משה | 050-1234567"}
    agreed["source"] = "agreed"
    verified = entry("לוי דוד", "03-1234567", rows=(2,))  # tie-breaker sure, verify yes
    verified["readings"] = {
        "claude": "לוי דור | 03-1234567",
        "gpt": "לוי דוד | 03-1234567",
        "tie-breaker": "לוי דוד | 03-1234567",
    }
    verified["source"] = "tie-breaker"
    refused = entry("פרץ רון", "6123456", rows=(3,))  # tie-breaker wrong, verify said no
    refused["readings"] = {
        "claude": "פרץ רות | 6123456",
        "gpt": "פרץ רון | 6123456",
        "tie-breaker": "פרץ רון | 6123456",
    }
    refused["issues"] = ["the readers disagree; the check said no to the tie-breaker"]
    got = {
        "contacts": [agreed, verified],
        "review_queue": [refused],
        "cost_usd": 0.3,
        "decisions": [
            {"node": "read_gpt", "cost_usd": 0.2},
            {"node": "read_claude", "cost_usd": 0},
        ],
    }

    names = {
        s: cli_score.score(truth, cli_score.stage_run(got, s))["names exact"]
        for s in cli_score.STAGES
    }
    assert names == {"claude": "2/3", "gpt": "2/3", "tie-breaker": "2/3", "final": "2/3"}
    assert cli_score.score(truth, cli_score.stage_run(got, "gpt"))["cost"] == "$0.2000"
    report = cli_score.verify_report(truth, got)
    assert (
        report == "verify: said yes to 1 right + 0 wrong names, said no to 0 right + 1 wrong names"
    )


def test_stages_reader_without_reading_misses_the_entry():
    truth = [{"rows": [1], "name": "כהן משה", "phones": ["050-1234567"]}]
    only_gpt = entry("כהן משה", "050-1234567")
    only_gpt["readings"] = {"gpt": "כהן משה | 050-1234567"}
    got = run([only_gpt])
    assert cli_score.score(truth, cli_score.stage_run(got, "claude"))["missing"] == 1
    assert cli_score.score(truth, cli_score.stage_run(got, "tie-breaker"))["names exact"] == "1/1"
    assert cli_score.verify_report(truth, got) == "verify: did not run"
