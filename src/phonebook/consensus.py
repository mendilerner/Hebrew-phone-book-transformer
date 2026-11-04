"""Compare the two readers (decision 0015). Pure Python: free, no LLM.

- Normalize, so small differences in writing don't count (spaces, ', -).
- Match entries by an agreed phone number, not by row number.
- Both read the same name and phones -> agreed. Otherwise -> a doubt for the tie-breaker.
"""

import re
from difflib import SequenceMatcher

from phonebook.phones import parse_phone
from phonebook.reads import Check, Doubt, EntryDraft, TieAnswer
from phonebook.schema import Contact

NAME_MATCH = 0.6  # name similarity needed to pair two entries that share no phone


def norm_phone(raw: str) -> str:
    """Digits and * only: '050-123 4567' -> '0501234567'."""
    return "".join(ch for ch in raw if ch.isdigit() or ch == "*")


def norm_name(name: str) -> str:
    """No quotes, geresh or dashes, one space between words: "דנה - כהנוביץ'" -> 'דנה כהנוביץ'."""
    name = re.sub(r"[\"'׳״`]", "", name)
    name = re.sub(r"[-־–—,.]", " ", name)
    return " ".join(name.split())


def phone_set(entry: EntryDraft) -> frozenset[str]:
    return frozenset(p for p in map(norm_phone, entry.phones) if p)


def same_reading(a: EntryDraft, b: EntryDraft) -> bool:
    return norm_name(a.name) == norm_name(b.name) and phone_set(a) == phone_set(b)


def reading_text(name: str, phones: list[str]) -> str:
    return f"{name} | {', '.join(phones)}" if phones else name


def pair_entries(
    claude: list[EntryDraft], gpt: list[EntryDraft]
) -> tuple[list[tuple[EntryDraft, EntryDraft]], list[EntryDraft], list[EntryDraft]]:
    """Pairs (claude, gpt), then the entries only Claude found, then only GPT found.

    First by a shared phone (phones are almost always read the same), then by a
    similar name. Each entry is used once.
    """
    left = list(gpt)
    pairs, only_claude = [], []
    for c in claude:
        match = next((g for g in left if phone_set(c) & phone_set(g)), None)
        if match is None:
            scored = [(_similar(c.name, g.name), i) for i, g in enumerate(left)]
            best = max(scored, default=(0.0, -1))
            match = left[best[1]] if best[0] >= NAME_MATCH else None
        if match is None:
            only_claude.append(c)
        else:
            left.remove(match)
            pairs.append((c, match))
    return pairs, only_claude, left


def compare(
    claude: list[EntryDraft], gpt: list[EntryDraft], page_no: int
) -> tuple[list[Contact], list[Doubt]]:
    """Returns the draft (agreed entries + entries only one reader found) and the doubts."""
    pairs, only_claude, only_gpt = pair_entries(claude, gpt)
    draft, doubts = [], []
    for c, g in pairs:
        readings = {"claude": _text(c), "gpt": _text(g)}
        if same_reading(c, g):
            confidence = min(c.confidence, g.confidence)
            draft.append(to_contact(c, page_no, "agreed", readings, confidence=confidence))
            continue
        # A and B alternate, so the tie-breaker can't learn "A is always Claude".
        a_is = "claude" if len(doubts) % 2 == 0 else "gpt"
        a, b = (c, g) if a_is == "claude" else (g, c)
        doubts.append(
            Doubt(id=len(doubts) + 1, anchor=_anchor(c, g), rows=c.rows, a=a, b=b, a_is=a_is)
        )
    for reader, other, entries in (("claude", "gpt", only_claude), ("gpt", "claude", only_gpt)):
        for e in entries:
            issue = f"only {reader} read this entry"
            draft.append(to_contact(e, page_no, None, {reader: _text(e)}, issues=[issue]))
    return draft, doubts


def resolve(doubt: Doubt, answer: TieAnswer | None, check: Check | None, page_no: int) -> Contact:
    """One doubt after tie_break and verify: a trusted contact, or one for the human."""
    by_reader = {doubt.a_is: doubt.a, _other(doubt.a_is): doubt.b}
    readings = {reader: _text(e) for reader, e in sorted(by_reader.items())}
    decided = answer is not None and answer.choice != "cant_tell"
    if decided:
        readings["tie-breaker"] = reading_text(answer.name, answer.phones)
    if decided and answer.sure and check is not None and check.matches:
        base = doubt.a if answer.choice == "A" else doubt.b if answer.choice == "B" else doubt.a
        entry = base.model_copy(update={"name": answer.name, "phones": answer.phones})
        return to_contact(entry, page_no, "tie-breaker", readings, confidence=0.9)

    if answer is None:
        issue = "the readers disagree"
    elif not decided:
        issue = "the readers disagree; the tie-breaker can't tell"
    elif not answer.sure:
        issue = "the readers disagree; the tie-breaker is not sure"
    else:
        issue = "the readers disagree; the check said no to the tie-breaker"
    entry = doubt.a
    if decided:
        entry = entry.model_copy(update={"name": answer.name, "phones": answer.phones})
    return to_contact(entry, page_no, None, readings, issues=[issue], confidence=0.0)


def to_contact(
    entry: EntryDraft,
    page_no: int,
    source: str | None,
    readings: dict[str, str],
    issues: list[str] | None = None,
    confidence: float | None = None,
) -> Contact:
    confidence = entry.confidence if confidence is None else confidence
    return Contact(
        name=entry.name,
        phones=[parse_phone(p) for p in entry.phones],
        address=entry.address,
        notes=entry.notes,
        extra={f.column: f.value for f in entry.extra},
        page=page_no,
        rows=entry.rows,
        confidence=min(max(confidence, 0.0), 1.0),
        issues=list(issues or []),
        source=source,
        readings=readings,
    )


def _anchor(c: EntryDraft, g: EntryDraft) -> str:
    shared = [p for p in c.phones if norm_phone(p) in phone_set(g)]
    if shared:
        return f"the row with phone {shared[0]}"
    rows = ", ".join(map(str, c.rows)) or "?"
    return f"row {rows} from the top"


def _text(e: EntryDraft) -> str:
    return reading_text(e.name, e.phones)


def _other(reader: str) -> str:
    return "gpt" if reader == "claude" else "claude"


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()
