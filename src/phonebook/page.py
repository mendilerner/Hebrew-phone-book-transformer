"""Page sub-graph nodes.

classify_page (L) -> read_page (A: an agent with tools) -> finalize_page
Later steps add: the retry loop, page_fix.
"""

from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, after_model
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from phonebook.cost import cost_usd
from phonebook.images import load_page, to_block
from phonebook.llm import ask_structured, chat_model, model_name, setting
from phonebook.phones import parse_phone
from phonebook.ruler import with_ruler
from phonebook.rules import check_contact
from phonebook.schema import Contact, Decision, LayoutProfile, PageState
from phonebook.tools import make_tools

# ---------------------------------------------------------------------------
# What the LLM returns. Rule: observations first, decision last (decision 0010).
# ---------------------------------------------------------------------------

PageKind = Literal["entries", "empty", "cover", "different_layout"]


class PageCheck(BaseModel):
    observations: str = Field(description="What you see on the page, before deciding")
    reason: str = Field(description="One short sentence: why this kind")
    kind: PageKind


class ExtraField(BaseModel):
    column: str = Field(description="Column header, or 'notes' if there is none")
    value: str


class EntryDraft(BaseModel):
    """One contact as the LLM reads it. Phones stay raw text; Python parses them."""

    rows: list[int] = Field(description="Row numbers from the top, starting at 1")
    name: str
    phones: list[str] = Field(description="Each number exactly as written")
    address: str | None = None
    notes: str | None = None
    extra: list[ExtraField] = Field(default_factory=list)
    doubts: list[str] = Field(
        default_factory=list, description="What you are not sure about, e.g. 'digit 4 or 9?'"
    )
    confidence: float = Field(description="0 to 1: how sure you are about this entry")


class PageRead(BaseModel):
    rows: list[str] = Field(description="The text of every row, top to bottom (the skeleton)")
    entries: list[EntryDraft]


CLASSIFY_PROMPT = """You check one page of a handwritten Hebrew phone book.
The book layout is described below. Decide what this page is:
- entries: contacts written in this layout
- empty: no contacts written
- cover: a cover, index or title page
- different_layout: contacts, but the columns don't match the layout
First write what you see, then decide.

Book layout:
{profile}"""

READ_PROMPT = """You read one page of a handwritten Hebrew phone book.
The book layout is described below. Read the WHOLE page, top to bottom.

The writing is by hand: often fast, messy, slanted or faded, by more than one person.
Many Hebrew letters look alike in handwriting, so look at each letter with care:
ר/ד/ך, ב/כ/פ, ה/ח/ת, ו/ז/ן/י, ס/ם/ט, ע/צ/ש, ג/נ, ק/ה, final letters (ך ם ן ף ץ).
Digits that look alike: 1/7, 4/9, 3/8, 5/6, 0/6.

Steps:
1. First write the text of every row (the skeleton), so nothing is skipped.
2. Then turn the rows into entries. One entry can use 2 rows (for example a name
   on one row and its phone on the next). Ink can cross the row lines.
3. Names, cities and streets: read the letter shapes first. Then use what you know
   about common Hebrew names. If the shapes fit a common name (for example a common
   family name like לרנר) better than a rare word (like לבקר), choose the common one.
   Use this only to choose between readings that the ink allows. Never change a
   name to one the ink does not show.
4. If you still can't decide, do not guess: write your best reading, put every
   possible reading in doubts (for example "לרנר or לבקר?"), and give a low
   confidence. Write ? for a letter you can't read at all.
5. Phone numbers: copy them exactly as written, digit by digit. General knowledge
   does not help here. Never add an area code. Write ? for an unclear digit and
   add a doubt (for example "digit 4 or 9?").
6. Put columns that are not name/phone/address/notes into extra.
7. confidence: about 0.9 or more only when every letter and digit is clear.

{tools}

Book layout:
{profile}"""


TOOLS_PROMPT = """Tools: you can look at parts of the page again, in full resolution.
The page has a red ruler (it is not part of the book): on the left, 0 = top and
100 = bottom of the page; on the top, 0 = left and 100 = right. Use these numbers
in the tools. Count the rows yourself from the top, starting at 1.
{tool_lines}
You have at most {max_calls} tool calls for this page.

How to work:
1. Look at the whole page and read every row.
2. Before your final answer, check the hardest rows with the tools: rows where a
   letter or digit is unclear. Use the calls on the rows you are least sure about.
3. Then give your final answer, with what you learned from the tools.
Answer without any tool call only when every entry is fully clear.
"""

NO_TOOLS_PROMPT = """The page has a red ruler (it is not part of the book). Count the rows
yourself from the top, starting at 1.
"""

# One line per tool for the prompt. Only the tools turned on are listed (setting agent_tools).
TOOL_LINES = {
    "zoom_band": "- zoom_band(top, bottom): a band across the page, bigger (small or unclear\n"
    "  letters and digits; take a taller band when ink crosses the row lines).",
    "crop_region": "- crop_region(x0, y0, x1, y1): any part of the page, for example a note.",
    "check_phone": "- check_phone(text): a free check of a phone number you read.",
}


def _profile_text(profile: LayoutProfile) -> str:
    return profile.model_dump_json(indent=2, exclude={"confirmed_by_human"})


def ask_page_kind(image_path: str, profile: LayoutProfile, model: str) -> tuple[PageCheck, float]:
    prompt = CLASSIFY_PROMPT.format(profile=_profile_text(profile))
    return ask_structured(PageCheck, prompt, [image_path], "What kind of page is this?", model)


def check_before_answer(min_confidence: float):
    """Agent middleware: an after_model hook (runs after every model turn).

    If the model gives its final answer without using any tool, while some entries
    have a low confidence, we send it back once: "check these rows first".
    jump_to="model" is how middleware changes the agent's flow.
    """

    @after_model(can_jump_to=["model"])
    def check(state, runtime):
        answer = state.get("structured_response")
        last = state["messages"][-1]
        used_tools = any(isinstance(m, ToolMessage) for m in state["messages"])
        asked_before = sum(isinstance(m, HumanMessage) for m in state["messages"]) > 1
        if answer is None or getattr(last, "tool_calls", None) or used_tools or asked_before:
            return None
        weak = [e for e in answer.entries if e.confidence < min_confidence]
        if not weak:
            return None
        weak.sort(key=lambda e: e.confidence)
        rows = ", ".join(str(e.rows[0]) for e in weak[:6] if e.rows)
        note = (
            f"Before the final answer, check the unclear rows with the tools "
            f"(for example zoom_band(top, bottom)). Least sure rows: {rows}. "
            "Then answer again."
        )
        return {"messages": [HumanMessage(note)], "jump_to": "model"}

    return check


def ask_read_page(
    image_path: str,
    profile: LayoutProfile,
    model: str,
    max_calls: int = 4,
    min_confidence: float = 0.8,
    tools: list[str] | None = None,
) -> tuple[PageRead, float]:
    """The read_page agent: the prebuilt create_agent (a model <-> tools loop graph).

    ToolCallLimitMiddleware stops the tools after `max_calls` calls, so the model
    must answer with what it has (decision 0008). ProviderStrategy gets the final
    answer as structured output with the provider's own JSON mode (decision 0010).

    `tools`: names of the tools to turn on (None = all). With no tools the agent
    is one model call, like build step 4. This lets you measure each tool.
    """
    img = load_page(image_path)
    page_tools = make_tools(img, tools)
    if page_tools:
        lines = "\n".join(TOOL_LINES[t.name] for t in page_tools)
        tools_text = TOOLS_PROMPT.format(tool_lines=lines, max_calls=max_calls)
        middleware = [
            ToolCallLimitMiddleware(run_limit=max_calls),
            check_before_answer(min_confidence),
        ]
    else:
        tools_text, middleware = NO_TOOLS_PROMPT, []
    prompt = READ_PROMPT.format(profile=_profile_text(profile), tools=tools_text)
    agent = create_agent(
        chat_model(model),
        tools=page_tools,
        system_prompt=prompt,
        response_format=ProviderStrategy(PageRead),
        middleware=middleware,
    )
    content = [to_block(with_ruler(img)), {"type": "text", "text": "Read this page."}]
    result = agent.invoke({"messages": [HumanMessage(content=content)]})
    # Every model turn of the agent costs money: add them all up.
    cost = sum(cost_usd(m, model) for m in result["messages"] if isinstance(m, AIMessage))
    return result["structured_response"], cost


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def classify_page(state: PageState, config: RunnableConfig) -> dict:
    model = model_name("classify_page", config)
    check, cost = ask_page_kind(state["image_path"], state["profile"], model)
    return {
        "page_kind": check.kind,
        "cost_usd": cost,
        "decisions": [_decision(state, "classify_page", check.kind, check.reason, model, cost)],
    }


def read_page(state: PageState, config: RunnableConfig) -> dict:
    model = model_name("read_page", config)
    max_calls = setting(config, "agent_tool_calls")
    min_confidence = setting(config, "min_confidence")
    tools = setting(config, "agent_tools")
    page, cost = ask_read_page(
        state["image_path"], state["profile"], model, max_calls, min_confidence, tools
    )
    draft = [_to_contact(entry, state["page_no"]) for entry in page.entries]
    if state["page_kind"] == "different_layout":
        for contact in draft:  # MVP has no rediscover_layout: read anyway, but let a human check
            contact.issues.append("page layout differs from the book")
    reason = f"{len(page.rows)} rows, {len(draft)} entries"
    return {
        "skeleton": page.rows,
        "draft": draft,
        "cost_usd": cost,
        "decisions": [_decision(state, "read_page", "read", reason, model, cost)],
    }


def finalize_page(state: PageState, config: RunnableConfig) -> dict:
    """Split the draft: good entries -> contacts, doubtful ones -> review_queue.

    These keys have the `add` reducer in the parent BookState, so every page
    appends its lists there (decision 0006).
    """
    min_confidence = setting(config, "min_confidence")
    good, doubtful = [], []
    for contact in state.get("draft", []):
        # a new object: never change state values in place
        contact = contact.model_copy(update={"issues": contact.issues + check_contact(contact)})
        ok = not contact.issues and contact.confidence >= min_confidence
        (good if ok else doubtful).append(contact)
    reason = f"{len(good)} good, {len(doubtful)} to review"
    return {
        "contacts": good,
        "review_queue": doubtful,
        "decisions": [_decision(state, "finalize_page", "done", reason)],
    }


# ---------------------------------------------------------------------------
# Router (L): the LLM's answer in classify_page picks the next node
# ---------------------------------------------------------------------------


def route_after_classify(state: PageState) -> str:
    if state["page_kind"] in ("empty", "cover"):
        return "skip"
    return "read_page"  # entries, or different_layout (MVP: no rediscover_layout yet)


# ---------------------------------------------------------------------------


def _to_contact(entry: EntryDraft, page_no: int) -> Contact:
    return Contact(
        name=entry.name,
        phones=[parse_phone(p) for p in entry.phones],
        address=entry.address,
        notes=entry.notes,
        extra={f.column: f.value for f in entry.extra},
        page=page_no,
        rows=entry.rows,
        confidence=min(max(entry.confidence, 0.0), 1.0),
        issues=list(entry.doubts),
    )


def _decision(
    state: PageState, node: str, choice: str, reason: str, model=None, cost=0.0
) -> Decision:
    reason = f"page {state['page_no']}: {reason}"
    return Decision(node=node, choice=choice, reason=reason, model=model, cost_usd=cost)
