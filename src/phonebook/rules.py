"""Free checks that run before any LLM grader (decision 0007).

Each check returns a list of `issues` (short texts). An empty list = looks fine.
"""

from phonebook.schema import Contact

# Final letters sort like their normal form (ך = כ).
_FINALS = str.maketrans("ךםןףץ", "כמנפצ")


def first_letter(name: str) -> str | None:
    """The first Hebrew letter of a name, final forms made normal. None if no Hebrew letter."""
    for char in name.strip():
        if "א" <= char <= "ת":
            return char.translate(_FINALS)
        if char.isalpha():
            return None  # starts with a non-Hebrew letter
    return None


def check_contact(contact: Contact) -> list[str]:
    issues = []
    if not contact.name.strip():
        issues.append("empty name")
    if not contact.phones:
        issues.append("no phone")
    for phone in contact.phones:
        if phone.kind == "unknown":
            issues.append(f"phone '{phone.raw}' looks wrong")
    return issues


def letter_order_issues(contacts: list[Contact]) -> dict[int, str]:
    """For a book sorted by letter: index -> issue, for entries that come back in the alphabet.

    Only the first letter is compared, so a page with names in any order inside
    one letter is fine.
    """
    issues: dict[int, str] = {}
    highest: str | None = None
    for i, contact in enumerate(contacts):
        letter = first_letter(contact.name)
        if letter is None:
            continue
        if highest and letter < highest:
            issues[i] = f"letter '{letter}' after '{highest}': wrong order or misread name"
        else:
            highest = letter
    return issues
