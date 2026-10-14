"""Book graph nodes for layout discovery (build step 3).

load_book -> discover_layout -> (R) more pages? -> confirm_layout (interrupt)
"""

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from phonebook.images import list_pages
from phonebook.llm import ask_structured, model_name
from phonebook.schema import BookState, Decision, LayoutProfile

MAX_EXTRA_TRIES = 2  # topology: discover_layout may look at 2 more pages

LAYOUT_PROMPT = """You look at sample pages of a handwritten Hebrew phone book.
Describe the LAYOUT of the book, not the contacts on these pages.

First write your observations for each page: printed headers, columns and
what is written in them, row lines, the Hebrew letter the page is for, and
anything unusual. Then fill in the profile from those observations:
- Columns in reading order (Hebrew: right to left) and what each holds.
- Printed row lines? Sorted by Hebrew letter? About how many rows per page?
- Quirks a reader must know (e.g. phones written across the name column).
Set clear=false if the pages don't agree or you can't see the layout well."""


class LayoutGuess(BaseModel):
    """What the LLM returns for discover_layout.

    Field order matters: the model writes the JSON top to bottom, so it writes
    what it SEES (observations) before it DECIDES (profile, clear).
    """

    observations: str = Field(description="What you see on each sample page, before deciding")
    profile: LayoutProfile
    reason: str = Field(description="One short sentence: why the layout is clear or not")
    clear: bool = Field(description="True if the layout is easy to see on these pages")


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def load_book(state: BookState) -> dict:
    """Find the page images and pick 2 sample pages from the middle of the book.

    The first and last pages are often a cover or empty, so we skip them.
    """
    pages = list_pages(state["book_id"])
    if not pages:
        raise ValueError(f"No page images (.jpg/.png) in {state['book_id']}")
    n = len(pages)
    samples = sorted({n // 3, (2 * n) // 3}) if n > 2 else list(range(n))
    return {"page_paths": pages, "sample_pages": samples}


def ask_layout_llm(image_paths: list[str], model: str) -> tuple[LayoutGuess, float]:
    """One LLM call with structured output. Returns the guess and its cost in $."""
    return ask_structured(LayoutGuess, LAYOUT_PROMPT, image_paths, "Describe the layout.", model)


def discover_layout(state: BookState, config: RunnableConfig) -> dict:
    model = model_name("discover_layout", config)
    paths = [state["page_paths"][i] for i in state["sample_pages"]]
    guess, cost = ask_layout_llm(paths, model)
    return {
        "profile": guess.profile,
        "layout_clear": guess.clear,
        "cost_usd": cost,
        "decisions": [
            Decision(
                node="discover_layout",
                choice="clear" if guess.clear else "unclear",
                reason=f"pages {state['sample_pages']}: {guess.reason}",
                model=model,
                cost_usd=cost,
            )
        ],
    }


def add_sample_page(state: BookState) -> dict:
    """Pick one more page that is not a sample yet (the one furthest from the others)."""
    used = set(state["sample_pages"])
    free = [i for i in range(len(state["page_paths"])) if i not in used]
    best = max(free, key=lambda i: min(abs(i - u) for u in used))
    return {"sample_pages": sorted(used | {best})}


def confirm_layout(state: BookState) -> dict:
    """Pause the graph and show the profile to the human (interrupt).

    Resume with Command(resume=...):
    - {"accept": True}           -> keep the profile
    - {"profile": {...fields}}   -> use the edited profile
    """
    answer = interrupt(
        {"question": "Is this layout right?", "profile": state["profile"].model_dump()}
    )
    if "profile" in answer:
        profile = LayoutProfile(**answer["profile"])
        choice = "edited"
    else:
        profile = state["profile"]
        choice = "accepted"
    return {
        "profile": profile.model_copy(update={"confirmed_by_human": True}),
        "decisions": [Decision(node="confirm_layout", choice=choice, reason="human answer")],
    }


# ---------------------------------------------------------------------------
# Router (R): a plain Python function on a conditional edge
# ---------------------------------------------------------------------------


def route_after_discover(state: BookState) -> str:
    extra_tries = len(state["sample_pages"]) - 2
    no_more_pages = len(state["sample_pages"]) >= len(state["page_paths"])
    if state["layout_clear"] or extra_tries >= MAX_EXTRA_TRIES or no_more_pages:
        return "confirm_layout"  # unclear after all tries: the human decides
    return "add_sample_page"
