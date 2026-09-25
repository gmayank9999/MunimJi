import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from seed_notion import _due_date_iso, _rich_text, _title  # noqa: E402


def test_due_date_iso_combines_base_and_invoice_offset():
    today = datetime.now(UTC).date()
    result = _due_date_iso(base_offset_days=26, due_offset_days=-11)
    expected_delta = 26 - 11
    assert result == str(today.fromordinal(today.toordinal() + expected_delta))


def test_title_shape():
    assert _title("INV-1077") == {"title": [{"text": {"content": "INV-1077"}}]}


def test_rich_text_shape():
    assert _rich_text("C01") == {"rich_text": [{"text": {"content": "C01"}}]}
