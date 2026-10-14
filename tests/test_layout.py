"""Layout discovery graph, with a fake LLM (no API calls, $0)."""

import pytest
from langgraph.types import Command
from PIL import Image

from phonebook import layout
from phonebook.book_graph import build_book_graph
from phonebook.images import image_block
from phonebook.schema import ColumnSpec, LayoutProfile

PROFILE = LayoutProfile(
    columns=[
        ColumnSpec(index=0, header="שם", meaning="name"),
        ColumnSpec(index=1, header="טלפון", meaning="phone"),
    ],
    has_printed_rows=True,
    sorted_by_letter=True,
)


@pytest.fixture
def book(tmp_path):
    for i in range(6):
        Image.new("RGB", (40, 60), "white").save(tmp_path / f"page_{i:02}.jpg")
    return str(tmp_path)


def fake_llm(monkeypatch, answers):
    """Replace the LLM call: return `answers` (True = clear) one by one, $0.01 each."""
    calls = []

    def fake(image_paths, model):
        calls.append(image_paths)
        clear = answers[len(calls) - 1]
        return layout.LayoutGuess(
            observations="fake", profile=PROFILE, reason="fake", clear=clear
        ), 0.01

    monkeypatch.setattr(layout, "ask_layout_llm", fake)
    return calls


def run_until_question(book):
    graph = build_book_graph()
    config = {"configurable": {"thread_id": "t1"}}
    return graph, config, graph.invoke({"book_id": book}, config)


def test_clear_layout_pauses_for_human(monkeypatch, book):
    calls = fake_llm(monkeypatch, [True])
    graph, config, result = run_until_question(book)

    assert len(calls) == 1 and len(calls[0]) == 2  # one call with 2 sample pages
    question = result["__interrupt__"][0].value
    assert question["profile"]["columns"][0]["header"] == "שם"

    done = graph.invoke(Command(resume={"accept": True}), config)
    assert done["profile"].confirmed_by_human
    assert [d.choice for d in done["decisions"]] == ["clear", "accepted"]
    assert done["cost_usd"] == pytest.approx(0.01)


def test_unclear_layout_looks_at_more_pages_then_stops(monkeypatch, book):
    calls = fake_llm(monkeypatch, [False, False, False])
    _, _, result = run_until_question(book)

    assert [len(c) for c in calls] == [2, 3, 4]  # one more page each try, max 2 extra tries
    assert "__interrupt__" in result  # after the last try the human decides
    assert result["cost_usd"] == pytest.approx(0.03)  # add reducer summed 3 calls


def test_human_can_edit_the_profile(monkeypatch, book):
    fake_llm(monkeypatch, [True])
    graph, config, _ = run_until_question(book)
    edited = PROFILE.model_dump() | {"rows_per_page": 25}
    done = graph.invoke(Command(resume={"profile": edited}), config)
    assert done["profile"].rows_per_page == 25
    assert done["decisions"][-1].choice == "edited"


def test_image_block_makes_big_photos_smaller(tmp_path):
    Image.new("RGB", (4000, 3000), "white").save(tmp_path / "big.jpg")
    block = image_block(tmp_path / "big.jpg")
    assert block["mime_type"] == "image/jpeg" and len(block["base64"]) < 200_000


def test_debug_mode_stops_at_the_question_and_resumes(monkeypatch, book, capsys):
    from phonebook.debug import run_graph

    fake_llm(monkeypatch, [True])
    graph = build_book_graph()
    config = {"configurable": {"thread_id": "debug"}}

    paused = run_graph(graph, {"book_id": book}, config, debug=True)
    assert "__interrupt__" in paused
    done = run_graph(graph, Command(resume={"accept": True}), config, debug=True)

    assert done["profile"].confirmed_by_human
    assert "INTERRUPT" in capsys.readouterr().err
