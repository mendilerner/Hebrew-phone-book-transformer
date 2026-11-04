"""State schema for the Hebrew phone book parser (LangGraph).

Two kinds of classes:
- Pydantic models  = the DATA (what the LLM returns with structured output).
- TypedDict states = what flows through the GRAPH (LangGraph state).

Three graph levels:
- BookState  -> parent graph (layout discovery, fan-out pages, merge, review, export)
- PageState  -> page sub-graph (one per page, started with Send)
- the row retry loop lives inside the page sub-graph (no own state)
"""

from operator import add
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from phonebook.reads import Check, Doubt, ModelRead, TieAnswer

# ---------------------------------------------------------------------------
# Data models (Pydantic)
# ---------------------------------------------------------------------------

FieldMeaning = Literal["name", "phone", "address", "city", "notes", "other"]


class ColumnSpec(BaseModel):
    index: int = Field(description="0 = first column in reading order (rightmost for RTL)")
    header: str | None = Field(description="Printed header text, e.g. 'שם'")
    meaning: FieldMeaning


class LayoutProfile(BaseModel):
    """What the graph learns about a book. Saved in the LangGraph Store."""

    columns: list[ColumnSpec]
    direction: Literal["rtl", "ltr"] = "rtl"
    has_printed_rows: bool
    sorted_by_letter: bool
    rows_per_page: int | None = None
    quirks: list[str] = Field(
        default_factory=list, description="e.g. 'phones cross into name column'"
    )
    confirmed_by_human: bool = False


class Phone(BaseModel):
    raw: str = Field(description="Exactly as written, e.g. '050-1234567' or '*9999'")
    digits: str | None = Field(description="Digits only; None if not a normal number")
    kind: Literal["mobile", "landline", "short_code", "unknown"] = "unknown"


class Contact(BaseModel):
    """The fixed OUTPUT format. Same for every book."""

    name: str
    phones: list[Phone]
    address: str | None = None
    notes: str | None = None
    extra: dict[str, str] = Field(default_factory=dict, description="Columns we don't know")
    page: int
    rows: list[int] = Field(description="A list, because one entry can span 2 rows")
    confidence: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list, description="Why a human must check it")
    # Who decided this entry (decision 0015): both readers agreed, the tie-breaker
    # (confirmed by the other model), or a human. None = not decided (review queue).
    source: Literal["agreed", "tie-breaker", "human"] | None = None
    # Every reading, for the human: {"claude": "name | phones", "gpt": ..., "tie-breaker": ...}
    readings: dict[str, str] = Field(default_factory=dict)


class Decision(BaseModel):
    """Audit log: every router/agent choice, so you can see WHY."""

    node: str
    choice: str
    reason: str
    model: str | None = None  # which LLM made this choice (None = rule or human)
    cost_usd: float = 0.0  # what that LLM call cost


# ---------------------------------------------------------------------------
# Graph states (TypedDict)
# ---------------------------------------------------------------------------


class PageState(TypedDict):
    # input (from Send)
    page_no: int
    image_path: str  # a path, not image bytes: keeps checkpoints small
    profile: LayoutProfile
    max_attempts: int
    page_budget_usd: float  # this page's share of the book budget (decision 0007)

    # working data (stays inside the page sub-graph)
    page_kind: Literal["entries", "empty", "cover", "different_layout"] | None
    # The two readers run in parallel and both write `reads`: a reducer is needed,
    # or LangGraph raises an error when two nodes write one key in the same step.
    reads: Annotated[list[ModelRead], add]
    skeleton: list[str]  # Claude's row texts from the full-page read
    draft: list[Contact]  # agreed entries, and entries only one reader found
    doubts: list[Doubt]  # rows where the readers disagree
    tie_answers: list[TieAnswer]  # the tie-breaker's answer per doubt
    checks: list[Check]  # the verifier's yes/no per sure answer

    # output (same key names as BookState -> merged by the reducers)
    contacts: Annotated[list[Contact], add]
    review_queue: Annotated[list[Contact], add]
    decisions: Annotated[list[Decision], add]
    cost_usd: Annotated[float, add]  # each LLM call returns its own cost; add sums them


class BookState(TypedDict):
    book_id: str
    page_paths: list[str]
    sample_pages: list[int]  # pages used for layout discovery
    profile: LayoutProfile | None
    layout_clear: bool  # discover_layout's answer: is the layout clear? (router reads it)
    max_attempts: int
    budget_usd: float  # max $ per book, default 10 (decision 0007)

    # filled by many pages in parallel -> need a reducer (add = append lists)
    contacts: Annotated[list[Contact], add]
    review_queue: Annotated[list[Contact], add]
    decisions: Annotated[list[Decision], add]
    cost_usd: Annotated[float, add]  # total spent; pages add their cost here

    output_files: list[str]  # Excel + .vcf paths
