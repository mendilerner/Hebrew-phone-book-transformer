"""Page sub-graph nodes (build step 7: two-model consensus, decision 0015).

classify_page (L) -> read_claude + read_gpt (in parallel) -> compare_reads (R)
  -> tie_break (Claude, only rows they disagree on) (R) -> verify (GPT) -> finalize_page
"""

from langchain_core.runnables import RunnableConfig

from phonebook import consensus
from phonebook.llm import ask_structured, model_name
from phonebook.reads import (  # noqa: F401  (re-exported: tests use page.EntryDraft etc.)
    Check,
    Doubt,
    EntryDraft,
    ExtraField,
    ModelRead,
    PageCheck,
    PageKind,
    PageRead,
    TieAnswer,
    TieBreak,
    Verify,
)
from phonebook.rules import check_contact
from phonebook.schema import Decision, LayoutProfile, PageState

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
6. A number is a phone only if it looks like one (7 or more digits, or a * code).
   Short numbers that are part of a name or address (a house number) stay there.
   A phone written in the name column still belongs to that entry's phones.
7. Ditto marks (״, '' or 〃) mean "same as the row above": write the text they stand for.
8. Put columns that are not name/phone/address/notes into extra.
9. confidence: about 0.9 or more only when every letter and digit is clear.

Book layout:
{profile}"""


LOOK_ALIKE = """Many Hebrew letters look alike in handwriting: ר/ד/ך, ב/כ/פ, ה/ח/ת, ו/ז/ן/י,
ס/ם/ט, ע/צ/ש, ג/נ, ק/ה, final letters (ך ם ן ף ץ). Digits: 1/7, 4/9, 3/8, 5/6, 0/6."""

TIE_PROMPT = """You check rows of one page of a handwritten Hebrew phone book.
Two readers read the page on their own and did not agree on the rows below.
Each row is pointed at by its phone number (or its row number from the top).

{look_alike}

For each row:
1. Find the row on the page and look at the ink, letter by letter.
2. observations: write what you see.
3. choice: A or B if it matches the ink exactly; new if both are wrong and you can
   read the row; cant_tell if you can't decide.
4. name and phones: the reading you chose, phones as written (empty for cant_tell).
5. sure: true when the ink clearly fits your reading better than any other reading,
   even if the handwriting is not perfect. A second model checks every sure answer
   against the page, so you don't need to be 100% certain. sure = false only when
   two readings still fit the ink equally well.

Book layout:
{profile}"""

VERIFY_PROMPT = """You check rows of one page of a handwritten Hebrew phone book.
For each row below, someone wrote down how it reads. Each row is pointed at by its
phone number (or its row number from the top).

{look_alike}

For each row: find it on the page, write what the ink shows (observations), then
matches = true only if the name and the phones are written exactly like this.
If any letter or digit is different, or you are not sure, matches = false.

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


def ask_tie_break(
    image_path: str, profile: LayoutProfile, doubts: list[Doubt], model: str
) -> tuple[TieBreak, float]:
    prompt = TIE_PROMPT.format(look_alike=LOOK_ALIKE, profile=_profile_text(profile))
    lines = [
        f"{d.id}. {d.anchor}: A = {consensus.reading_text(d.a.name, d.a.phones)!r}, "
        f"B = {consensus.reading_text(d.b.name, d.b.phones)!r}"
        for d in doubts
    ]
    return ask_structured(TieBreak, prompt, [image_path], "\n".join(lines), model)


def ask_verify(
    image_path: str, profile: LayoutProfile, items: list[tuple[Doubt, TieAnswer]], model: str
) -> tuple[Verify, float]:
    prompt = VERIFY_PROMPT.format(look_alike=LOOK_ALIKE, profile=_profile_text(profile))
    lines = [f"{d.id}. {d.anchor}: {consensus.reading_text(a.name, a.phones)!r}" for d, a in items]
    return ask_structured(Verify, prompt, [image_path], "\n".join(lines), model)


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


def _reader(node: str, reader: str):
    """A read node. read_claude and read_gpt are the same code with another model."""

    def read(state: PageState, config: RunnableConfig) -> dict:
        model = model_name(node, config)
        page, cost = ask_read_page(state["image_path"], state["profile"], model)
        reason = f"{len(page.rows)} rows, {len(page.entries)} entries"
        return {
            # `reads` has the add reducer: both readers append to it in the same step
            "reads": [ModelRead(reader=reader, model=model, page=page)],
            "cost_usd": cost,
            "decisions": [_decision(state, node, "read", reason, model, cost)],
        }

    read.__name__ = node
    return read


read_claude = _reader("read_claude", "claude")
read_gpt = _reader("read_gpt", "gpt")


def compare_reads(state: PageState) -> dict:
    """Free: agreed entries -> draft, disagreements -> doubts (decision 0015)."""
    by_reader = {r.reader: r.page for r in state["reads"]}
    claude, gpt = by_reader["claude"], by_reader["gpt"]
    draft, doubts = consensus.compare(claude.entries, gpt.entries, state["page_no"])
    agreed = sum(c.source == "agreed" for c in draft)
    reason = f"{agreed} agreed, {len(doubts)} doubts, {len(draft) - agreed} found by one reader"
    return {
        "skeleton": claude.rows,
        "draft": draft,
        "doubts": doubts,
        "decisions": [_decision(state, "compare_reads", "compared", reason)],
    }


def tie_break(state: PageState, config: RunnableConfig) -> dict:
    """One call for all doubts of the page: the full page, readings A and B."""
    model = model_name("tie_break", config)
    result, cost = ask_tie_break(state["image_path"], state["profile"], state["doubts"], model)
    sure = sum(_is_sure(a) for a in result.answers)
    reason = f"{sure} of {len(state['doubts'])} sure"
    return {
        "tie_answers": result.answers,
        "cost_usd": cost,
        "decisions": [_decision(state, "tie_break", "answered", reason, model, cost)],
    }


def verify(state: PageState, config: RunnableConfig) -> dict:
    """The other model checks every sure answer: yes/no. Two models agree, or a human looks."""
    model = model_name("verify", config)
    doubts = {d.id: d for d in state["doubts"]}
    items = [(doubts[a.id], a) for a in state["tie_answers"] if _is_sure(a) and a.id in doubts]
    result, cost = ask_verify(state["image_path"], state["profile"], items, model)
    yes = sum(c.matches for c in result.checks)
    reason = f"{yes} of {len(items)} confirmed"
    return {
        "checks": result.checks,
        "cost_usd": cost,
        "decisions": [_decision(state, "verify", "checked", reason, model, cost)],
    }


def finalize_page(state: PageState) -> dict:
    """Split: trusted entries -> contacts, the rest -> review_queue (with every reading).

    These keys have the `add` reducer in the parent BookState, so every page
    appends its lists there (decision 0006).
    """
    answers = {a.id: a for a in state.get("tie_answers", [])}
    checks = {c.id: c for c in state.get("checks", [])}
    page_no = state["page_no"]
    entries = list(state.get("draft", [])) + [
        consensus.resolve(d, answers.get(d.id), checks.get(d.id), page_no)
        for d in state.get("doubts", [])
    ]
    good, doubtful = [], []
    for contact in entries:
        issues = contact.issues + check_contact(contact)
        if state["page_kind"] == "different_layout":  # MVP: no rediscover_layout yet
            issues.append("page layout differs from the book")
        # a new object: never change state values in place
        source = contact.source if not issues else None
        contact = contact.model_copy(update={"issues": issues, "source": source})
        (good if source else doubtful).append(contact)
    reason = f"{len(good)} good, {len(doubtful)} to review"
    return {
        "contacts": good,
        "review_queue": doubtful,
        "decisions": [_decision(state, "finalize_page", "done", reason)],
    }


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


def route_after_classify(state: PageState) -> list[str] | str:
    """L: the LLM's page kind decides. A list of nodes = run them in parallel."""
    if state["page_kind"] in ("empty", "cover"):
        return "skip"
    return ["read_claude", "read_gpt"]  # entries, or different_layout (no rediscover yet)


def route_after_compare(state: PageState) -> str:
    """R: only pay for a tie-break when the readers disagree somewhere."""
    return "tie_break" if state.get("doubts") else "finalize_page"


def route_after_tie_break(state: PageState) -> str:
    """R: verify only the answers the tie-breaker is sure about."""
    return "verify" if any(map(_is_sure, state.get("tie_answers", []))) else "finalize_page"


# ---------------------------------------------------------------------------


def _is_sure(answer: TieAnswer) -> bool:
    return answer.sure and answer.choice != "cant_tell"


def _decision(
    state: PageState, node: str, choice: str, reason: str, model=None, cost=0.0
) -> Decision:
    reason = f"page {state['page_no']}: {reason}"
    return Decision(node=node, choice=choice, reason=reason, model=model, cost_usd=cost)
