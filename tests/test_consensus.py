"""Compare the two readers: free Python, made-up numbers."""

from phonebook import consensus
from phonebook.reads import EntryDraft


def entry(name, *phones, rows=(1,)):
    return EntryDraft(rows=list(rows), name=name, phones=list(phones), confidence=0.9)


def test_normalize():
    assert consensus.norm_phone("050-123 4567") == "0501234567"
    assert consensus.norm_phone("*9999") == "*9999"
    assert consensus.norm_name("בן-דוד  -  מוסך (2001)") == "בן דוד מוסך (2001)"
    assert consensus.norm_name("כהנוביץ' שרה") == "כהנוביץ שרה"


def test_pairs_by_phone_then_by_name():
    claude = [entry("כהן", "050-1111111"), entry("לוי דוד", "052-2222222"), entry("שקד")]
    gpt = [entry("לוי דור", "052-2222229"), entry("כהן", "0501111111")]
    pairs, only_claude, only_gpt = consensus.pair_entries(claude, gpt)
    assert [(c.name, g.name) for c, g in pairs] == [("כהן", "כהן"), ("לוי דוד", "לוי דור")]
    assert [e.name for e in only_claude] == ["שקד"] and only_gpt == []


def test_doubts_alternate_a_and_b_and_point_at_the_phone():
    claude = [entry("א1", "050-1111111"), entry("ב1", "050-2222222", rows=(2,))]
    gpt = [entry("א2", "050-1111111"), entry("ב2", "050-2222222", rows=(2,))]
    draft, doubts = consensus.compare(claude, gpt, page_no=1)
    assert draft == []
    assert [d.a_is for d in doubts] == ["claude", "gpt"]
    assert [d.a.name for d in doubts] == ["א1", "ב2"]
    assert doubts[0].anchor == "the row with phone 050-1111111"


def test_no_shared_phone_points_at_the_row():
    _draft, doubts = consensus.compare(
        [entry("שמעוני", "050-1112223", rows=(15,))], [entry("שמעוני", "050-1112999")], page_no=1
    )
    assert doubts[0].anchor == "row 15 from the top"
