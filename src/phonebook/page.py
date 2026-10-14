"""Page sub-graph nodes (build step 4: the simple version).

classify_page (L) -> read_page -> finalize_page
Later steps add: agent tools in read_page, the retry loop, page_fix.
"""

from typing import Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from phonebook.llm import ask_structured, model_name, setting
from phonebook.phones import parse_phone
from phonebook.rules import check_contact
from phonebook.schema import Contact, Decision, LayoutProfile, PageState

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
1. First write the text of every row (the skeleton), so nothing is skipped.
2. Then turn the rows into entries. One entry can use 2 rows (for example a name
   on one row and its phone on the next). Ink can cross the row lines.
3. Copy phone numbers exactly as written. Never add an area code.
4. Put columns that are not name/phone/address/notes into extra.
5. Write every doubt, and give a low confidence when you guess.

Book layout:
{profile}"""


def _profile_text(profile: LayoutProfile) -> str:
    return profile.model_dump_json(indent=2, exclude={"confirmed_by_human"})


def ask_page_kind(image_path: str, profile: LayoutProfile, model: str) -> tuple[PageCheck, float]:
    prompt = CLASSIFY_PROMPT.format(profile=_profile_text(profile))
    return ask_structured(PageCheck, prompt, [image_path], "What kind of page is this?", model)


def ask_read_page(image_path: str, profile: LayoutProfile, model: str) -> tuple[PageRead, float]:
    prompt = READ_PROMPT.format(profile=_profile_text(profile))
    return ask_structured(PageRead, prompt, [image_path], "Read this page.", model)


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
    page, cost = ask_read_page(state["image_path"], state["profile"], model)
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
