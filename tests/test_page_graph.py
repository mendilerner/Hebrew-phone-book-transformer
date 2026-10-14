"""Page sub-graph with a fake LLM (no API calls, $0). All numbers are made up."""

import pytest

from phonebook import page
from phonebook.page_graph import build_page_graph
from phonebook.schema import ColumnSpec, LayoutProfile

PROFILE = LayoutProfile(
    columns=[
        ColumnSpec(index=0, header="שם", meaning="name"),
        ColumnSpec(index=1, header="טלפון", meaning="phone"),
    ],
    has_printed_rows=True,
    sorted_by_letter=True,
    confirmed_by_human=True,
)


def page_input(page_no=3):
    return {"page_no": page_no, "image_path": "page.jpg", "profile": PROFILE, "max_attempts": 3}


def entry(name, *phones, confidence=0.95, doubts=(), rows=(1,)):
    return page.EntryDraft(
        rows=list(rows), name=name, phones=list(phones), confidence=confidence, doubts=list(doubts)
    )


def fake_llm(monkeypatch, kind, entries=()):
    calls = []

    def fake_kind(image_path, profile, model):
        calls.append(("classify", model))
        return page.PageCheck(observations="fake", reason="fake", kind=kind), 0.001

    def fake_read(image_path, profile, model):
        calls.append(("read", model))
        rows = [e.name for e in entries]
        return page.PageRead(rows=rows, entries=list(entries)), 0.01

    monkeypatch.setattr(page, "ask_page_kind", fake_kind)
    monkeypatch.setattr(page, "ask_read_page", fake_read)
    return calls


def test_good_and_doubtful_entries_are_split(monkeypatch):
    entries = [
        entry("כהן משה", "050-1234567"),
        entry("לוי", "050-12345"),  # rule check: a digit is missing
        entry("מזרחי", "03-1234567", confidence=0.5, doubts=["3 or 8?"]),
        entry("פרץ דוד", "6123456", rows=(4, 5)),  # entry on 2 rows, old 7-digit number
    ]
    calls = fake_llm(monkeypatch, "entries", entries)
    out = build_page_graph().invoke(page_input())

    assert [c.name for c in out["contacts"]] == ["כהן משה", "פרץ דוד"]
    assert [c.name for c in out["review_queue"]] == ["לוי", "מזרחי"]
    assert out["review_queue"][0].issues == ["phone '050-12345' looks wrong"]
    assert out["review_queue"][1].issues == ["3 or 8?"]
    assert out["contacts"][1].rows == [4, 5] and out["contacts"][1].page == 3
    assert out["cost_usd"] == pytest.approx(0.011)
    assert calls == [
        ("classify", "anthropic:claude-haiku-5-5"),
        ("read", "anthropic:claude-haiku-5-5"),
    ]


@pytest.mark.parametrize("kind", ["empty", "cover"])
def test_empty_or_cover_page_is_skipped(monkeypatch, kind):
    calls = fake_llm(monkeypatch, kind)
    out = build_page_graph().invoke(page_input())
    assert [c[0] for c in calls] == ["classify"]  # no read call: saves money
    assert out.get("contacts", []) == []
    assert out["decisions"][0].choice == kind


def test_different_layout_is_read_but_sent_to_review(monkeypatch):
    fake_llm(monkeypatch, "different_layout", [entry("כהן", "050-1234567")])
    out = build_page_graph().invoke(page_input())
    assert out.get("contacts", []) == []
    assert out["review_queue"][0].issues == ["page layout differs from the book"]


def test_model_comes_from_config(monkeypatch):
    calls = fake_llm(monkeypatch, "entries", [entry("כהן", "050-1234567")])
    config = {"configurable": {"tiers": {"read_page": "strong"}}}
    build_page_graph().invoke(page_input(), config)
    assert calls[1] == ("read", "anthropic:claude-sonnet-5-5")


def test_decisions_record_model_and_cost(monkeypatch):
    fake_llm(monkeypatch, "entries", [entry("כהן", "050-1234567")])
    out = build_page_graph().invoke(page_input())
    by_node = {d.node: d for d in out["decisions"]}
    assert by_node["read_page"].model == "anthropic:claude-haiku-5-5"
    assert by_node["read_page"].cost_usd == pytest.approx(0.01)
    assert by_node["finalize_page"].model is None  # a rule, not an LLM


def test_cli_page_tier_best_uses_opus_and_saves_json(monkeypatch, tmp_path):
    import json

    from phonebook import cli_page

    calls = fake_llm(monkeypatch, "entries", [entry("כהן משה", "050-1234567")])
    profile_file = tmp_path / "profile.json"
    profile_file.write_text(PROFILE.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(cli_page, "PROFILE_FILE", profile_file)
    monkeypatch.setattr(cli_page, "OUTPUT_DIR", tmp_path / "output")

    result = cli_page.run_page("p05.jpg", tier="best")
    path = cli_page.save_json(result, "p05.jpg", "best")

    assert {model for _, model in calls} == {"anthropic:claude-opus-5-5"}
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "p05.best.json"
    assert saved["models"]["read_page"] == "anthropic:claude-opus-5-5"
    assert saved["contacts"][0]["name"] == "כהן משה"
    assert "כהן משה" in path.read_text(encoding="utf-8")  # Hebrew is not escaped


def test_debug_mode_prints_steps_and_gives_same_result(monkeypatch, capsys):
    from phonebook.debug import run_graph

    fake_llm(monkeypatch, "entries", [entry("כהן משה", "050-1234567")])
    out = run_graph(build_page_graph(), page_input(), {}, debug=True)
    printed = capsys.readouterr().err
    assert "STEP 1: classify_page" in printed and "STEP 3: finalize_page" in printed
    assert "כהן משה" in printed  # Hebrew is readable
    assert [c.name for c in out["contacts"]] == ["כהן משה"]


def test_debug_hides_image_data():
    from langchain_core.messages import HumanMessage

    from phonebook.debug import format_message

    message = HumanMessage(content=[{"type": "image", "base64": "A" * 5000}, "Read this page."])
    text = format_message(message)
    assert "<image data, 5000 chars>" in text and "AAAA" not in text
