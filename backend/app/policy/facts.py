from datetime import date, datetime, timedelta
from datetime import time as dt_time
from typing import Literal

from pydantic import BaseModel

from app.policy.config import PolicyConfig

ClientTier = Literal["VIP", "Regular", "New", "Watchlist"]
PromiseStatus = Literal["none", "pending", "broken", "kept"]
ResponseCategory = Literal[
    "NO_RESPONSE", "ACKNOWLEDGED", "PROMISE_TO_PAY", "DISPUTE", "CLAIMS_PAID",
    "EXTENSION_REQUEST", "REFUND_REQUEST", "HOSTILE", "OTHER",
]

PAID_STATUSES = {"PAID", "MARKED_AS_PAID"}
REFUNDED_STATUSES = {"REFUNDED", "MARKED_AS_REFUNDED"}


class InvoiceFacts(BaseModel):
    invoice_id: str
    number: str
    client_id: str
    client_name: str
    client_tier: ClientTier
    paypal_status: str
    amount_inr: int
    due_inr: int
    paid_inr: int
    invoice_date: date
    due_date: date
    as_of: datetime
    days_overdue: int
    days_since_issue: int
    is_partially_paid: bool
    reminder_count: int
    hours_since_last_reminder: float | None
    last_client_msg_at: datetime | None
    unanswered_reminders: int
    promise_date: date | None
    promise_status: PromiseStatus
    dispute_open: bool
    refund_requested_inr: int | None
    paused_until: date | None
    in_quiet_hours: bool
    is_business_day: bool
    open_jira_key: str | None
    client_open_exposure_inr: int


class ResponseSignal(BaseModel):
    category: ResponseCategory
    promise_date: date | None = None
    claimed_payment_date: date | None = None
    claimed_reference: str | None = None
    dispute_reason: str | None = None
    requested_extension_until: date | None = None
    refund_amount_inr: int | None = None
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    key_quote: str = ""
    confidence: float = 1.0
    source_message_id: str | None = None


def _in_quiet_hours(as_of: datetime, quiet_start: str, quiet_end: str) -> bool:
    start_t = dt_time.fromisoformat(quiet_start)
    end_t = dt_time.fromisoformat(quiet_end)
    now_t = as_of.time()
    if start_t <= end_t:
        return start_t <= now_t < end_t
    # window wraps midnight, e.g. 21:00 -> 09:00
    return now_t >= start_t or now_t < end_t


def _promise_status(
    promise_date: date | None, as_of: datetime, promise_grace_days: int, is_paid: bool
) -> PromiseStatus:
    if promise_date is None:
        return "none"
    if is_paid:
        return "kept"
    if as_of.date() <= promise_date + timedelta(days=promise_grace_days):
        return "pending"
    return "broken"


def build_facts(
    *,
    invoice_id: str,
    number: str,
    client_id: str,
    client_name: str,
    client_tier: ClientTier,
    paypal_status: str,
    amount_inr: int,
    due_inr: int,
    paid_inr: int,
    invoice_date: date,
    due_date: date,
    as_of: datetime,
    config: PolicyConfig,
    reminder_timestamps: list[datetime] | None = None,
    last_client_msg_at: datetime | None = None,
    promise_date: date | None = None,
    dispute_open: bool = False,
    refund_requested_inr: int | None = None,
    paused_until: date | None = None,
    open_jira_key: str | None = None,
    client_open_exposure_inr: int = 0,
) -> InvoiceFacts:
    reminder_timestamps = reminder_timestamps or []

    is_paid = paypal_status in PAID_STATUSES
    effective_due_inr = 0 if is_paid else due_inr

    days_overdue = max(0, (as_of.date() - due_date).days)
    days_since_issue = max(0, (as_of.date() - invoice_date).days)
    is_partially_paid = 0 < paid_inr < amount_inr

    reminder_count = len(reminder_timestamps)
    hours_since_last_reminder = (
        (as_of - max(reminder_timestamps)).total_seconds() / 3600 if reminder_timestamps else None
    )

    if last_client_msg_at is None:
        unanswered_reminders = reminder_count
    else:
        unanswered_reminders = sum(1 for t in reminder_timestamps if t > last_client_msg_at)

    promise_status = _promise_status(promise_date, as_of, config.promise_grace_days, is_paid)

    return InvoiceFacts(
        invoice_id=invoice_id,
        number=number,
        client_id=client_id,
        client_name=client_name,
        client_tier=client_tier,
        paypal_status=paypal_status,
        amount_inr=amount_inr,
        due_inr=effective_due_inr,
        paid_inr=paid_inr,
        invoice_date=invoice_date,
        due_date=due_date,
        as_of=as_of,
        days_overdue=days_overdue,
        days_since_issue=days_since_issue,
        is_partially_paid=is_partially_paid,
        reminder_count=reminder_count,
        hours_since_last_reminder=hours_since_last_reminder,
        last_client_msg_at=last_client_msg_at,
        unanswered_reminders=unanswered_reminders,
        promise_date=promise_date,
        promise_status=promise_status,
        dispute_open=dispute_open,
        refund_requested_inr=refund_requested_inr,
        paused_until=paused_until,
        in_quiet_hours=_in_quiet_hours(as_of, config.quiet_hours.start, config.quiet_hours.end),
        is_business_day=as_of.weekday() < 5,
        open_jira_key=open_jira_key,
        client_open_exposure_inr=client_open_exposure_inr,
    )
