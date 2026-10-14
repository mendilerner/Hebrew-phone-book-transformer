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
