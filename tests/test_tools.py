"""Row lines, agent tools and the read_page agent, with drawn pages and a fake LLM ($0)."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from PIL import Image, ImageDraw

from phonebook import page
from phonebook.ruler import with_ruler
from phonebook.schema import ColumnSpec, LayoutProfile
from phonebook.tools import make_tools


def drawn_page() -> Image.Image:
    """A white page with some lines and 'writing' (a plain test picture)."""
    img = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(img)
    for i in range(11):
        draw.line((40, 200 + 100 * i, 1160, 206 + 100 * i), fill=(255, 182, 193), width=3)
    draw.rectangle((300, 240, 700, 270), fill="black")
    return img


def test_ruler_is_drawn_next_to_the_page():
    img = drawn_page()
    ruled = with_ruler(img)
    assert ruled.width > img.width and ruled.height > img.height
    strip = round(img.width * 0.06)
    page_area = (strip, strip, strip + img.width, strip + img.height)
    assert ruled.crop(page_area).tobytes() == img.tobytes()  # nothing drawn on the page


def tools_by_name(img):
    return {t.name: t for t in make_tools(img)}


def test_zoom_band_returns_two_halves():
    tools = tools_by_name(drawn_page())
    zoom = tools["zoom_band"].invoke({"top": 12, "bottom": 19})
    assert [b["type"] for b in zoom] == ["text", "image", "text", "image"]
    assert "Use 0 <= top < bottom" in tools["zoom_band"].invoke({"top": 50, "bottom": 40})


def test_crop_region():
    tools = tools_by_name(drawn_page())
    crop = tools["crop_region"].invoke({"x0": 10, "y0": 10, "x1": 30, "y1": 20})
    assert crop[1]["type"] == "image"
    assert "Use 0 <= x0" in tools["crop_region"].invoke({"x0": 0, "y0": 0, "x1": 120, "y1": 5})


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
            tool_calls=[{"name": "zoom_band", "args": {"top": 12, "bottom": 19}, "id": "t1"}],
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
        AIMessage(
            "", tool_calls=[{"name": "zoom_band", "args": {"top": 30, "bottom": 36}, "id": "t1"}]
        ),
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
