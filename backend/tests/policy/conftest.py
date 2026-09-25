from datetime import date, datetime
from typing import Any

import pytest

from app.clock import IST
from app.policy.facts import InvoiceFacts, ResponseSignal

FACTS_DEFAULTS: dict[str, Any] = dict(
    invoice_id="inv_test",
    number="INV-9000",
    client_id="c_test",
    client_name="Test Client",
    client_tier="Regular",
    paypal_status="SENT",
    amount_inr=20000,
    due_inr=20000,
    paid_inr=0,
    invoice_date=date(2026, 9, 1),
    due_date=date(2026, 9, 10),
    as_of=datetime(2026, 9, 10, 12, 0, tzinfo=IST),
    days_overdue=0,
    days_since_issue=9,
    is_partially_paid=False,
    reminder_count=0,
    hours_since_last_reminder=None,
    last_client_msg_at=None,
    unanswered_reminders=0,
    promise_date=None,
    promise_status="none",
    dispute_open=False,
    refund_requested_inr=None,
    paused_until=None,
    in_quiet_hours=False,
    is_business_day=True,
    open_jira_key=None,
    client_open_exposure_inr=20000,
)

SIGNAL_DEFAULTS: dict[str, Any] = dict(
    category="NO_RESPONSE",
    promise_date=None,
    claimed_payment_date=None,
    claimed_reference=None,
    dispute_reason=None,
    requested_extension_until=None,
    refund_amount_inr=None,
    sentiment="neutral",
    key_quote="",
    confidence=1.0,
    source_message_id=None,
)


def make_facts(**overrides: Any) -> InvoiceFacts:
    data = {**FACTS_DEFAULTS, **overrides}
    return InvoiceFacts.model_validate(data)


def make_signal(**overrides: Any) -> ResponseSignal:
    data = {**SIGNAL_DEFAULTS, **overrides}
    return ResponseSignal.model_validate(data)


@pytest.fixture
def facts():
    return make_facts


@pytest.fixture
def signal():
    return make_signal
