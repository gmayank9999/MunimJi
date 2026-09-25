import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from seed_stripe import _compute_base_offset_days, _inr_to_usd_cents  # noqa: E402


def test_base_offset_covers_most_overdue_invoice_with_one_day_buffer():
    invoices = [{"due_offset_days": -6}, {"due_offset_days": -25}, {"due_offset_days": 5}]
    assert _compute_base_offset_days(invoices) == 26


def test_base_offset_is_at_least_one_when_nothing_is_overdue():
    invoices = [{"due_offset_days": 5}, {"due_offset_days": 10}]
    assert _compute_base_offset_days(invoices) == 1


def test_base_offset_handles_empty_list():
    assert _compute_base_offset_days([]) == 1


def test_inr_to_usd_cents_matches_known_conversion():
    # 85000 / 83.0 = 1024.096... -> $1024.10 -> 102410 cents
    assert _inr_to_usd_cents(85000, 83.0) == 102410
