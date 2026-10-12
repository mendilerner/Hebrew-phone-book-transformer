"""State schema draft for the Hebrew phone book parser (LangGraph).

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
    quirks: list[str] = Field(default_factory=list, description="e.g. 'phones cross into name column'")
    confirmed_by_human: bool = False


class Phone(BaseModel):
    raw: str = Field(description="Exactly as written, e.g. '054-5947474' or '*3140'")
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
    issues: list[str] = Field(default_factory=list, description="What the grader found")


class Decision(BaseModel):
    """Audit log: every router/agent choice, so you can see WHY."""

    node: str
    choice: str
    reason: str


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
    skeleton: list[str]  # rough row texts from the full-page read
    draft: list[Contact]  # entries being checked / retried
    attempts: dict[int, int]  # row -> retries used

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
    max_attempts: int
    budget_usd: float  # max $ per book, default 10 (decision 0007)

    # filled by many pages in parallel -> need a reducer (add = append lists)
    contacts: Annotated[list[Contact], add]
    review_queue: Annotated[list[Contact], add]
    decisions: Annotated[list[Decision], add]
    cost_usd: Annotated[float, add]  # total spent; pages add their cost here

    output_files: list[str]  # Excel + .vcf paths
