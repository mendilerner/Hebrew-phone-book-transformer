"""Page sub-graph with fake LLMs (no API calls, $0). All numbers are made up."""

import json

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
OPUS = "anthropic:claude-opus-5-5"
GPT = "openai:gpt-6-astra"


def page_input(page_no=3):
    return {"page_no": page_no, "image_path": "page.jpg", "profile": PROFILE, "max_attempts": 3}


def entry(name, *phones, confidence=0.95, rows=(1,)):
    return page.EntryDraft(rows=list(rows), name=name, phones=list(phones), confidence=confidence)


def fake_llm(monkeypatch, kind, claude=(), gpt=(), answers=(), checks=()):
    """claude / gpt: what each reader returns. answers / checks: tie_break and verify."""
    calls = []

    def fake_kind(image_path, profile, model):
        calls.append(("classify", model))
        return page.PageCheck(observations="fake", reason="fake", kind=kind), 0.001

    def fake_read(image_path, profile, model):
        calls.append(("read", model))
        entries = list(gpt if model.startswith("openai:") else claude)
        return page.PageRead(rows=[e.name for e in entries], entries=entries), 0.01

    def fake_tie(image_path, profile, doubts, model):
        calls.append(("tie_break", model, [d.id for d in doubts]))
        return page.TieBreak(answers=list(answers)), 0.02

    def fake_verify(image_path, profile, items, model):
        calls.append(("verify", model, [d.id for d, _ in items]))
        return page.Verify(checks=list(checks)), 0.005

    monkeypatch.setattr(page, "ask_page_kind", fake_kind)
    monkeypatch.setattr(page, "ask_read_page", fake_read)
    monkeypatch.setattr(page, "ask_tie_break", fake_tie)
    monkeypatch.setattr(page, "ask_verify", fake_verify)
    return calls


def answer(id, choice, name="", *phones, sure=True):
    return page.TieAnswer(
        id=id, observations="fake", choice=choice, name=name, phones=list(phones), sure=sure
    )


def test_both_agree_no_tie_break(monkeypatch):
    same = [entry("כהן משה", "050-1234567"), entry("פרץ דוד", "6123456", rows=(4, 5))]
    calls = fake_llm(monkeypatch, "entries", claude=same, gpt=same)
    out = build_page_graph().invoke(page_input())

    assert [c.name for c in out["contacts"]] == ["כהן משה", "פרץ דוד"]
    assert {c.source for c in out["contacts"]} == {"agreed"}
    assert out["review_queue"] == []
    assert out["contacts"][1].rows == [4, 5] and out["contacts"][1].page == 3
    # both readers ran (in parallel), and nothing else was paid for
    assert sorted(c[1] for c in calls if c[0] == "read") == [OPUS, GPT]
    assert not [c for c in calls if c[0] in ("tie_break", "verify")]
    assert out["cost_usd"] == pytest.approx(0.021)


def test_small_writing_differences_still_agree(monkeypatch):
    fake_llm(
        monkeypatch,
        "entries",
        claude=[entry("דנה - כהנוביץ'", "050-123 4567")],
        gpt=[entry("דנה כהנוביץ", "0501234567")],
    )
    out = build_page_graph().invoke(page_input())
    assert [c.source for c in out["contacts"]] == ["agreed"]


def test_disagreement_sure_and_confirmed_is_trusted(monkeypatch):
    calls = fake_llm(
        monkeypatch,
        "entries",
        claude=[entry("כהן משה", "050-1234567"), entry("לוי דוד", "052-7654321", rows=(2,))],
        gpt=[entry("כהן משה", "050-1234567"), entry("לוי דור", "052-7654321", rows=(2,))],
        answers=[answer(1, "A", "לוי דוד", "052-7654321")],
        checks=[page.Check(id=1, observations="fake", matches=True)],
    )
    out = build_page_graph().invoke(page_input())

    trusted = {c.name: c for c in out["contacts"]}
    assert trusted["לוי דוד"].source == "tie-breaker"
    assert trusted["לוי דוד"].readings == {
        "claude": "לוי דוד | 052-7654321",
        "gpt": "לוי דור | 052-7654321",
        "tie-breaker": "לוי דוד | 052-7654321",
    }
    assert ("tie_break", OPUS, [1]) in calls and ("verify", GPT, [1]) in calls


def test_verify_says_no_goes_to_review(monkeypatch):
    fake_llm(
        monkeypatch,
        "entries",
        claude=[entry("לוי דוד", "052-7654321")],
        gpt=[entry("לוי דור", "052-7654321")],
        answers=[answer(1, "new", "לוי דוב", "052-7654321")],
        checks=[page.Check(id=1, observations="fake", matches=False)],
    )
    out = build_page_graph().invoke(page_input())
    assert out["contacts"] == []
    [review] = out["review_queue"]
    assert review.source is None and "the check said no" in review.issues[0]
    assert set(review.readings) == {"claude", "gpt", "tie-breaker"}


@pytest.mark.parametrize("tie", [answer(1, "cant_tell"), answer(1, "B", "לוי דור", sure=False)])
def test_not_sure_skips_verify_and_goes_to_review(monkeypatch, tie):
    calls = fake_llm(
        monkeypatch,
        "entries",
        claude=[entry("לוי דוד", "052-7654321")],
        gpt=[entry("לוי דור", "052-7654321")],
        answers=[tie],
    )
    out = build_page_graph().invoke(page_input())
    assert [c.name for c in out["review_queue"]] == ["לוי דור" if tie.sure is False else "לוי דוד"]
    assert not [c for c in calls if c[0] == "verify"]  # nothing sure: no check paid for


def test_phones_that_differ_are_a_doubt(monkeypatch):
    calls = fake_llm(
        monkeypatch,
        "entries",
        claude=[entry("שמעוני", "050-1112223")],
        gpt=[entry("שמעוני", "050-1112999")],
        answers=[answer(1, "cant_tell")],
    )
    out = build_page_graph().invoke(page_input())
    assert ("tie_break", OPUS, [1]) in calls
    assert [c.name for c in out["review_queue"]] == ["שמעוני"]


def test_entry_only_one_reader_found_goes_to_review(monkeypatch):
    fake_llm(
        monkeypatch,
        "entries",
        claude=[entry("כהן משה", "050-1234567"), entry("מזרחי", "03-1234567", rows=(2,))],
        gpt=[entry("כהן משה", "050-1234567")],
    )
    out = build_page_graph().invoke(page_input())
    assert [c.name for c in out["contacts"]] == ["כהן משה"]
    assert out["review_queue"][0].issues == ["only claude read this entry"]


def test_rule_check_still_sends_agreed_entry_to_review(monkeypatch):
    same = [entry("לוי", "050-12345")]  # a digit is missing
    fake_llm(monkeypatch, "entries", claude=same, gpt=same)
    out = build_page_graph().invoke(page_input())
    assert out["contacts"] == []
    assert out["review_queue"][0].issues == ["phone '050-12345' looks wrong"]


@pytest.mark.parametrize("kind", ["empty", "cover"])
def test_empty_or_cover_page_is_skipped(monkeypatch, kind):
    calls = fake_llm(monkeypatch, kind)
    out = build_page_graph().invoke(page_input())
    assert [c[0] for c in calls] == ["classify"]  # no read call: saves money
    assert out.get("contacts", []) == []
    assert out["decisions"][0].choice == kind


def test_different_layout_is_read_but_sent_to_review(monkeypatch):
    same = [entry("כהן", "050-1234567")]
    fake_llm(monkeypatch, "different_layout", claude=same, gpt=same)
    out = build_page_graph().invoke(page_input())
    assert out.get("contacts", []) == []
    assert out["review_queue"][0].issues == ["page layout differs from the book"]


def test_model_comes_from_config(monkeypatch):
    same = [entry("כהן", "050-1234567")]
    calls = fake_llm(monkeypatch, "entries", claude=same, gpt=same)
    config = {"configurable": {"tiers": {"read_claude": "strong"}}}
    build_page_graph().invoke(page_input(), config)
    assert ("read", "anthropic:claude-sonnet-5-5") in calls


def test_decisions_record_model_and_cost(monkeypatch):
    same = [entry("כהן", "050-1234567")]
    fake_llm(monkeypatch, "entries", claude=same, gpt=same)
    out = build_page_graph().invoke(page_input())
    by_node = {d.node: d for d in out["decisions"]}
    assert by_node["read_gpt"].model == GPT
    assert by_node["read_claude"].cost_usd == pytest.approx(0.01)
    assert by_node["compare_reads"].model is None  # a rule, not an LLM
    assert by_node["compare_reads"].reason == "page 3: 1 agreed, 0 doubts, 0 found by one reader"


def test_tie_break_never_sees_who_read_what():
    doubts = [
        page.Doubt(
            id=1,
            anchor="the row with phone 1",
            rows=[1],
            a=entry("A1"),
            b=entry("B1"),
            a_is="claude",
        )
    ]
    seen = {}

    def fake_ask(schema, system, images, text, model):
        seen["prompt"] = system + text
        return page.TieBreak(answers=[]), 0.0

    import phonebook.page as module

    original = module.ask_structured
    module.ask_structured = fake_ask
    try:
        page.ask_tie_break("page.jpg", PROFILE, doubts, OPUS)
    finally:
        module.ask_structured = original
    text = seen["prompt"].lower()
    assert "a = 'a1'" in text and "b = 'b1'" in text
    assert "claude" not in text and "gpt" not in text


def test_cli_page_saves_json_with_readings(monkeypatch, tmp_path):
    from phonebook import cli_page

    calls = fake_llm(
        monkeypatch,
        "entries",
        claude=[entry("כהן משה", "050-1234567")],
        gpt=[entry("כהן משה", "050-1234567")],
    )
    profile_file = tmp_path / "profile.json"
    profile_file.write_text(PROFILE.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(cli_page, "PROFILE_FILE", profile_file)
    monkeypatch.setattr(cli_page, "OUTPUT_DIR", tmp_path / "output")

    result = cli_page.run_page("p05.jpg", tier="strong")
    path = cli_page.save_json(result, "p05.jpg", "strong")

    assert ("read", "anthropic:claude-sonnet-5-5") in calls and ("read", GPT) in calls
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "p05.strong.json"
    assert saved["models"]["read_gpt"] == GPT
    assert saved["contacts"][0]["source"] == "agreed"
    assert "כהן משה" in path.read_text(encoding="utf-8")  # Hebrew is not escaped


def test_debug_mode_prints_steps_and_gives_same_result(monkeypatch, capsys):
    from phonebook.debug import run_graph

    same = [entry("כהן משה", "050-1234567")]
    fake_llm(monkeypatch, "entries", claude=same, gpt=same)
    out = run_graph(build_page_graph(), page_input(), {}, debug=True)
    printed = capsys.readouterr().err
    assert "classify_page" in printed and "compare_reads" in printed
    assert "כהן משה" in printed  # Hebrew is readable
    assert [c.name for c in out["contacts"]] == ["כהן משה"]


def test_debug_hides_image_data():
    from langchain_core.messages import HumanMessage

    from phonebook.debug import format_message

    message = HumanMessage(content=[{"type": "image", "base64": "A" * 5000}, "Read this page."])
    text = format_message(message)
    assert "<image data, 5000 chars>" in text and "AAAA" not in text
