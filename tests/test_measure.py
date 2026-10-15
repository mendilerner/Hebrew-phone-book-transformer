"""Tools to measure each agent tool: one tool by hand, tool sets, and the score. $0."""

import json

import pytest
from PIL import Image

from phonebook import cli_page, cli_score, cli_tool, page
from phonebook.tools import make_tools


def test_make_tools_can_pick_tools():
    img = Image.new("RGB", (100, 100), "white")
    assert [t.name for t in make_tools(img, ["check_phone"])] == ["check_phone"]
    assert make_tools(img, []) == []
    with pytest.raises(ValueError):
        make_tools(img, ["magic"])


def test_cli_tool_saves_what_the_model_sees(monkeypatch, tmp_path):
    path = tmp_path / "page.jpg"
    Image.new("RGB", (1200, 1600), "white").save(path)
    monkeypatch.setattr(cli_tool, "OUTPUT_DIR", tmp_path / "tool")
    lines = cli_tool.run_tool(str(path), "zoom_band", ["30", "36"])
    assert lines[0] == "band 30-36: right half"
    assert len(list((tmp_path / "tool").glob("*.jpg"))) == 2
    assert "ruler.jpg" in cli_tool.run_tool(str(path), "ruler", [])[0]
    assert '"mobile"' in cli_tool.run_tool(str(path), "check_phone", ["050-1234567"])[0]


def test_run_name_shows_the_tool_set():
    assert cli_page.run_name("s/p05.jpg", "strong", None) == "p05.strong"
    assert cli_page.run_name("s/p05.jpg", "strong", []) == "p05.strong.no-tools"
    assert cli_page.run_name("s/p05.jpg", None, ["zoom_band"]) == "p05.default.zoom_band"


def test_no_tools_prompt_has_no_tool_section(monkeypatch, tmp_path):
    path = tmp_path / "page.jpg"
    Image.new("RGB", (400, 600), "white").save(path)
    seen = {}

    def fake_agent(model, tools, system_prompt, response_format, middleware):
        seen.update(tools=tools, prompt=system_prompt, middleware=middleware)
        raise StopIteration

    monkeypatch.setattr(page, "create_agent", fake_agent)
    monkeypatch.setattr(page, "chat_model", lambda name: None)
    profile = page.LayoutProfile(columns=[], has_printed_rows=True, sorted_by_letter=True)
    with pytest.raises(StopIteration):
        page.ask_read_page(str(path), profile, "m", tools=[])
    assert seen["tools"] == [] and seen["middleware"] == []
    assert "zoom_band" not in seen["prompt"] and "Count the rows" in seen["prompt"]


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


def test_tools_label_in_the_output():
    assert cli_page._tools_label(None) == "all"
    assert cli_page._tools_label([]) == "none"
    assert cli_page._tools_label(["zoom_band"]) == ["zoom_band"]
