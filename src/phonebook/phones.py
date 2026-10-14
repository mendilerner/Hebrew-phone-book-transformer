"""Turn a phone number as written into a `Phone` (no LLM, free).

Israeli rules:
- mobile:     05X + 7 digits = 10 digits (054-5947474)
- landline:   02/03/04/08/09 + 7 digits = 9 digits, 07X + 7 digits = 10 digits,
              1-700 / 1-800 numbers = 10 digits
- old number: 7 digits, no area code. Kept as written: we never add an area
              code (decision 0002).
- short code: a star and 2-5 digits (*3140)
Anything else is "unknown", so the grader can flag it.
"""

import re

from phonebook.schema import Phone

_SHORT_CODE = re.compile(r"^\*\d{2,5}$")
_LANDLINE_AREAS = ("02", "03", "04", "08", "09")


def parse_phone(raw: str) -> Phone:
    raw = raw.strip()
    compact = re.sub(r"[\s\-./()]", "", raw)

    if _SHORT_CODE.match(compact):
        return Phone(raw=raw, digits=None, kind="short_code")

    if compact.startswith("+972"):
        compact = "0" + compact[4:]
    if not compact.isdigit():
        return Phone(raw=raw, digits=None, kind="unknown")

    return Phone(raw=raw, digits=compact, kind=_kind(compact))


def _kind(digits: str) -> str:
    if len(digits) == 10 and digits.startswith("05"):
        return "mobile"
    if len(digits) == 9 and digits.startswith(_LANDLINE_AREAS):
        return "landline"
    if len(digits) == 10 and digits.startswith(("07", "1700", "1800")):
        return "landline"
    if len(digits) == 7 and digits[0] != "0":
        return "landline"  # old number without area code
    return "unknown"
