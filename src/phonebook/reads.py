"""What the LLMs return (structured output), and the data built from it.

Rule for every LLM answer: observations first, decision last (decision 0010).
"""

from typing import Literal

from pydantic import BaseModel, Field

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


class ModelRead(BaseModel):
    """One reader's result. `reader` is "claude" or "gpt"."""

    reader: Literal["claude", "gpt"]
    model: str
    page: PageRead


class Doubt(BaseModel):
    """A row where the two readers disagree. The LLM sees only A and B, not who wrote them."""

    id: int
    anchor: str = Field(description="How to find the row, e.g. 'the row with phone 0501234567'")
    rows: list[int]
    a: EntryDraft
    b: EntryDraft
    a_is: Literal["claude", "gpt"]  # hidden from the tie-breaker


class TieAnswer(BaseModel):
    id: int
    observations: str = Field(description="What the ink shows in this row, letter by letter")
    choice: Literal["A", "B", "new", "cant_tell"]
    name: str = Field(description="The name you chose; empty for cant_tell")
    phones: list[str] = Field(description="The phones you chose, as written; empty for cant_tell")
    sure: bool = Field(description="True only if every letter and digit is clear on the page")


class TieBreak(BaseModel):
    answers: list[TieAnswer]


class Check(BaseModel):
    id: int
    observations: str = Field(description="What the ink shows in this row")
    matches: bool = Field(description="True only if the name and phones are exactly as written")


class Verify(BaseModel):
    checks: list[Check]
