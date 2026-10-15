"""Row lines, agent tools and the read_page agent, with drawn pages and a fake LLM ($0)."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from PIL import Image, ImageDraw

from phonebook import page
from phonebook.rows import find_row_lines, ink_crosses_line, with_row_numbers
from phonebook.schema import ColumnSpec, LayoutProfile
from phonebook.tools import make_tools

LINE_YS = [200 + 100 * i for i in range(11)]  # 11 lines -> 10 rows


def drawn_page(tilt=6) -> Image.Image:
    """A white page with printed lines (a bit tilted, like a photo) and some 'writing'."""
    img = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(img)
    for y in LINE_YS:
        draw.line((40, y, 1160, y + tilt), fill="black", width=3)
    draw.rectangle((300, 240, 700, 270), fill="black")  # writing inside row 1
    draw.rectangle((300, 470, 330, 530), fill="black")  # a long stroke over line 4 (row 3/4)
    return img


def test_finds_the_printed_lines():
    rows = find_row_lines(drawn_page())
    assert rows.row_count == 10
    assert all(abs(found - y) <= 6 for found, y in zip(rows.ys, LINE_YS, strict=True))


def test_no_lines_means_no_rows():
    assert find_row_lines(Image.new("RGB", (800, 1000), "white")).row_count == 0


def test_ink_crosses_line():
    img = drawn_page()
    rows = find_row_lines(img)
    assert ink_crosses_line(img, rows, 1) == {"above": False, "below": False}
    assert ink_crosses_line(img, rows, 3)["below"] is True  # the stroke over line 4


def test_row_numbers_are_drawn_next_to_the_page():
    img = drawn_page()
    numbered = with_row_numbers(img, find_row_lines(img))
    assert numbered.height == img.height and numbered.width > img.width


def tools_by_name(img):
    return {t.name: t for t in make_tools(img, find_row_lines(img))}


def test_row_view_returns_images():
    tools = tools_by_name(drawn_page())
    strip = tools["row_view"].invoke({"row": 2, "mode": "strip"})
    assert [b["type"] for b in strip] == ["text", "image"]
    zoom = tools["row_view"].invoke({"row": 2, "mode": "zoom"})
    assert [b["type"] for b in zoom] == ["text", "image", "text", "image"]
    assert "No row 99" in tools["row_view"].invoke({"row": 99})


def test_tools_without_lines_say_use_crop():
    tools = tools_by_name(Image.new("RGB", (800, 1000), "white"))
    assert "crop_region" in tools["row_view"].invoke({"row": 1})
    crop = tools["crop_region"].invoke({"x0": 0.1, "y0": 0.1, "x1": 0.3, "y1": 0.2})
    assert crop[1]["type"] == "image"


def test_check_phone():
    tools = tools_by_name(drawn_page())
    assert tools["check_phone"].invoke({"text": "050-1234567"})["kind"] == "mobile"


# --- the agent, with a fake model --------------------------------------------


class FakeToolModel(GenericFakeChatModel):
    """A fake chat model that 'supports' tools: it answers from a fixed list."""

    def bind_tools(self, tools, **kwargs):
        return self


PROFILE = LayoutProfile(
    columns=[ColumnSpec(index=0, header="שם", meaning="name")],
    has_printed_rows=True,
    sorted_by_letter=True,
)


def test_read_page_agent_uses_a_tool_then_answers(monkeypatch, tmp_path):
    path = tmp_path / "page.jpg"
    drawn_page().save(path)
    answer = {
        "rows": ["כהן משה 050-1234567"],
        "entries": [{"rows": [1], "name": "כהן משה", "phones": ["050-1234567"], "confidence": 0.9}],
    }
    usage = {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}
    replies = [
        AIMessage(
            "",
            tool_calls=[{"name": "row_view", "args": {"row": 1, "mode": "zoom"}, "id": "t1"}],
            usage_metadata=usage,
        ),
        AIMessage(json.dumps(answer, ensure_ascii=False), usage_metadata=usage),
    ]
    fake = FakeToolModel(messages=iter(replies))
    monkeypatch.setattr(page, "chat_model", lambda name: fake)

    result, cost = page.ask_read_page(str(path), PROFILE, "anthropic:claude-haiku-5-5")

    assert result.entries[0].name == "כהן משה"
    assert cost == pytest.approx(2 * (1000 * 0.10 + 100 * 0.50) / 1_000_000)  # both turns


def test_debug_shows_the_agent_steps_inside_read_page(monkeypatch, tmp_path, capsys):
    from phonebook.debug import run_graph
    from phonebook.page_graph import build_page_graph

    path = tmp_path / "page.jpg"
    drawn_page().save(path)
    monkeypatch.setattr(
        page,
        "ask_page_kind",
        lambda *a: (page.PageCheck(observations="", reason="", kind="entries"), 0.0),
    )
    answer = {"rows": ["x"], "entries": []}
    fake = FakeToolModel(messages=iter([AIMessage(json.dumps(answer))]))
    monkeypatch.setattr(page, "chat_model", lambda name: fake)

    state = {"page_no": 1, "image_path": str(path), "profile": PROFILE, "max_attempts": 3}
    run_graph(build_page_graph(), state, {}, debug=tmp_path / "debug.txt")
    tree = capsys.readouterr().out
    assert "    read_page agent > model" in tree  # indented: a step inside read_page
    assert "model gives its final answer" in tree


def test_debug_hides_images_in_tool_messages():
    from langchain_core.messages import ToolMessage

    from phonebook.debug import _json

    message = ToolMessage(content=[{"type": "image", "base64": "A" * 5000}], tool_call_id="t1")
    assert "AAAA" not in _json({"messages": [message]})


def test_agent_is_sent_back_once_to_check_unclear_rows(monkeypatch, tmp_path):
    path = tmp_path / "page.jpg"
    drawn_page().save(path)

    def answer(confidence):
        entry = {"rows": [3], "name": "כהן", "phones": ["050-1234567"], "confidence": confidence}
        return AIMessage(json.dumps({"rows": ["כהן"], "entries": [entry]}, ensure_ascii=False))

    replies = [
        answer(0.4),  # answers at once, unsure, no tools -> the middleware sends it back
        AIMessage("", tool_calls=[{"name": "row_view", "args": {"row": 3}, "id": "t1"}]),
        answer(0.9),
    ]
    seen = []

    class Recorder(FakeToolModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages)
            return super()._generate(messages, *args, **kwargs)

    fake = Recorder(messages=iter(replies))
    monkeypatch.setattr(page, "chat_model", lambda name: fake)

    result, _ = page.ask_read_page(str(path), PROFILE, "anthropic:claude-haiku-5-5")

    assert len(seen) == 3
    assert "Least sure rows: 3" in seen[1][-1].content
    assert result.entries[0].confidence == 0.9


def test_cli_rows_saves_a_preview(monkeypatch, tmp_path):
    from phonebook import cli_rows

    path = tmp_path / "page.jpg"
    drawn_page().save(path)
    monkeypatch.setattr(cli_rows, "OUTPUT_DIR", tmp_path / "output")
    saved, count = cli_rows.preview(str(path))
    assert count == 10 and saved.exists()
