"""Write the final contacts to Excel and to .vcf (no LLM, free)."""

from pathlib import Path

from openpyxl import Workbook

from phonebook.schema import Contact


def export_excel(contacts: list[Contact], path: str | Path) -> Path:
    """One row per contact, one column per phone. Phones are text, so a leading 0 stays."""
    max_phones = max((len(c.phones) for c in contacts), default=1)
    extra_keys = sorted({key for c in contacts for key in c.extra})
    header = (
        ["name"]
        + [f"phone {i + 1}" for i in range(max_phones)]
        + ["address", "notes"]
        + extra_keys
        + ["page", "rows", "confidence", "issues"]
    )

    sheet_book = Workbook()
    sheet = sheet_book.active
    sheet.title = "contacts"
    sheet.sheet_view.rightToLeft = True
    sheet.append(header)
    for c in contacts:
        phones = [p.raw for p in c.phones] + [""] * (max_phones - len(c.phones))
        sheet.append(
            [c.name]
            + phones
            + [c.address or "", c.notes or ""]
            + [c.extra.get(key, "") for key in extra_keys]
            + [c.page, ", ".join(map(str, c.rows)), c.confidence, "; ".join(c.issues)]
        )
    for row in sheet.iter_rows(min_row=2, min_col=2, max_col=1 + max_phones):
        for cell in row:
            cell.number_format = "@"  # text, not a number

    path = Path(path)
    sheet_book.save(path)
    return path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def to_vcard(contact: Contact) -> str:
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{_escape(contact.name)}"]
    lines.append(f"N:{_escape(contact.name)};;;;")
    for phone in contact.phones:
        kind = "CELL" if phone.kind == "mobile" else "VOICE"
        lines.append(f"TEL;TYPE={kind}:{phone.digits or phone.raw}")
    if contact.address:
        lines.append(f"ADR:;;{_escape(contact.address)};;;;")
    if contact.notes:
        lines.append(f"NOTE:{_escape(contact.notes)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def export_vcf(contacts: list[Contact], path: str | Path) -> Path:
    """One vCard per contact that has a mobile number (decision: .vcf is for the phone)."""
    cards = [to_vcard(c) for c in contacts if any(p.kind == "mobile" for p in c.phones)]
    path = Path(path)
    path.write_text("".join(cards), encoding="utf-8")
    return path
