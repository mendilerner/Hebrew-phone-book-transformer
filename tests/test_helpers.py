# All numbers here are made up. Never put real numbers from the phone book in tests.
import pytest
from openpyxl import load_workbook

from phonebook.export import export_excel, export_vcf, to_vcard
from phonebook.phones import parse_phone
from phonebook.rules import check_contact, first_letter, letter_order_issues
from phonebook.schema import Contact


@pytest.mark.parametrize(
    "raw, digits, kind",
    [
        ("050-1234567", "0501234567", "mobile"),
        ("054 123 4567", "0541234567", "mobile"),
        ("+972-52-1234567", "0521234567", "mobile"),
        ("03-1234567", "031234567", "landline"),
        ("077-1234567", "0771234567", "landline"),
        ("1-800-123-456", "1800123456", "landline"),
        ("6123456", "6123456", "landline"),  # old 7-digit number: no area code added
        ("*3140", None, "short_code"),
        ("050-12345", "05012345", "unknown"),  # a digit is missing
        ("05O-1234567", None, "unknown"),  # letter O instead of 0
    ],
)
def test_parse_phone(raw, digits, kind):
    phone = parse_phone(raw)
    assert (phone.raw, phone.digits, phone.kind) == (raw, digits, kind)


def contact(name, *phones, **kw):
    return Contact(
        name=name, phones=[parse_phone(p) for p in phones], page=1, rows=[1], confidence=1.0, **kw
    )


def test_check_contact():
    assert check_contact(contact("כהן משה", "050-1234567")) == []
    assert check_contact(contact("", "050-1234567")) == ["empty name"]
    assert check_contact(contact("לוי")) == ["no phone"]
    assert check_contact(contact("לוי", "050-12345")) == ["phone '050-12345' looks wrong"]


def test_first_letter():
    assert first_letter("  כהן") == "כ"
    assert first_letter("ךכה") == "כ"  # final form counts as the normal letter
    assert first_letter("(דוד) אבי") == "ד"
    assert first_letter("Moshe") is None


def test_letter_order():
    names = ["אבי", "אורי", "בני", "אהרון", "גדי"]
    contacts = [contact(n, "050-1234567") for n in names]
    assert list(letter_order_issues(contacts)) == [3]  # אהרון after ב


def test_export_excel_keeps_phones_as_text(tmp_path):
    rows = [
        contact("כהן", "050-1234567", "03-1234567", extra={"עיר": "חיפה"}),
        contact("לוי", "6123456", notes="דוד"),
    ]
    sheet = load_workbook(export_excel(rows, tmp_path / "out.xlsx"))["contacts"]
    header = [c.value for c in sheet[1]]
    assert header[:3] == ["name", "phone 1", "phone 2"]
    assert "עיר" in header
    assert sheet["B2"].value == "050-1234567"  # leading 0 kept
    assert sheet["B3"].value == "6123456"


def test_vcf_only_for_contacts_with_mobile(tmp_path):
    rows = [contact("כהן, משה", "050-1234567", "*3140"), contact("לוי", "03-1234567")]
    text = export_vcf(rows, tmp_path / "out.vcf").read_text(encoding="utf-8")
    assert text.count("BEGIN:VCARD") == 1
    assert "FN:כהן\\, משה" in text
    assert "TEL;TYPE=CELL:0501234567" in text
    assert "TEL;TYPE=VOICE:*3140" in text


def test_vcard_shape():
    card = to_vcard(contact("כהן", "050-1234567", address="הרצל 1", notes="דוד"))
    assert card.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n")
    assert card.endswith("END:VCARD\r\n")
    assert "ADR:;;הרצל 1;;;;" in card and "NOTE:דוד" in card
