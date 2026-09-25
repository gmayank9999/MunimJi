from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel

from app.policy.config import PolicyConfig
from app.policy.facts import PAID_STATUSES, REFUNDED_STATUSES, InvoiceFacts, ResponseSignal

Decision = Literal[
    "CLOSE", "WAIT", "FOLLOWUP", "HIGH_PRIORITY", "ESCALATE",
    "DISPUTE_ROUTE", "RECONCILE", "CRITICAL", "HANDOVER",
]

Predicate = Callable[[InvoiceFacts, ResponseSignal, PolicyConfig], bool]
ReasonFn = Callable[[InvoiceFacts, ResponseSignal, PolicyConfig], str]


class DecisionResult(BaseModel):
    decision: Decision
    rule_id: str
    reason: str


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    decision: Decision
    predicate: Predicate
    reason: ReasonFn


def _paypal_verified_payment(facts: InvoiceFacts) -> bool:
    """Whether PayPal shows at least one payment against this invoice.

    R03 already closes fully-paid invoices before this is reached, so this only
    matters for a claimed payment PayPal partially corroborates (paid_inr > 0
    without the invoice being fully settled).
    """
    return facts.paid_inr > 0


RULES: list[Rule] = [
    Rule(
        id="R01",
        label="paypal-dispute",
        decision="CRITICAL",
        predicate=lambda f, s, c: f.dispute_open,
        reason=lambda f, s, c: "Open PayPal dispute on this invoice's payment",
    ),
    Rule(
        id="R02",
        label="refund-request",
        decision="CRITICAL",
        predicate=lambda f, s, c: s.category == "REFUND_REQUEST",
        reason=lambda f, s, c: "Client requested a refund",
    ),
    Rule(
        id="R03",
        label="paid-close",
        decision="CLOSE",
        predicate=lambda f, s, c: f.paypal_status in PAID_STATUSES or f.due_inr == 0,
        reason=lambda f, s, c: "Invoice is paid in full",
    ),
    Rule(
        id="R04",
        label="refunded-close",
        decision="CLOSE",
        predicate=lambda f, s, c: f.paypal_status in REFUNDED_STATUSES,
        reason=lambda f, s, c: "Invoice was refunded",
    ),
    Rule(
        id="R05",
        label="owner-paused",
        decision="WAIT",
        predicate=lambda f, s, c: f.paused_until is not None and f.paused_until >= f.as_of.date(),
        reason=lambda f, s, c: f"Paused by owner until {f.paused_until}",
    ),
    Rule(
        id="R06",
        label="client-dispute",
        decision="DISPUTE_ROUTE",
        predicate=lambda f, s, c: s.category == "DISPUTE",
        reason=lambda f, s, c: s.dispute_reason or "Client disputes the deliverable/service",
    ),
    Rule(
        id="R07",
        label="claims-paid",
        decision="RECONCILE",
        predicate=lambda f, s, c: s.category == "CLAIMS_PAID" and not _paypal_verified_payment(f),
        reason=lambda f, s, c: "Client claims payment but PayPal shows none",
    ),
    Rule(
        id="R08",
        label="claims-paid-verified",
        decision="CLOSE",
        predicate=lambda f, s, c: s.category == "CLAIMS_PAID" and _paypal_verified_payment(f),
        reason=lambda f, s, c: "Client claims payment and PayPal confirms it",
    ),
    Rule(
        id="R09",
        label="promise-pending",
        decision="WAIT",
        predicate=lambda f, s, c: f.promise_status == "pending",
        reason=lambda f, s, c: f"Promise pending until {f.promise_date + timedelta(days=c.promise_grace_days)}",
    ),
    Rule(
        id="R10",
        label="promise-broken-big",
        decision="ESCALATE",
        predicate=lambda f, s, c: f.promise_status == "broken" and f.due_inr >= c.escalate_amount_inr,
        reason=lambda f, s, c: f"Promised payment by {f.promise_date} but still unpaid, {f.due_inr} due",
    ),
    Rule(
        id="R11",
        label="promise-broken",
        decision="HIGH_PRIORITY",
        predicate=lambda f, s, c: f.promise_status == "broken",
        reason=lambda f, s, c: f"Promised payment by {f.promise_date} but still unpaid",
    ),
    Rule(
        id="R12",
        label="extension-reasonable",
        decision="WAIT",
        predicate=lambda f, s, c: (
            s.category == "EXTENSION_REQUEST"
            and s.requested_extension_until is not None
            and (s.requested_extension_until - f.due_date).days <= 14
            and f.client_tier != "Watchlist"
        ),
        reason=lambda f, s, c: f"Reasonable extension requested to {s.requested_extension_until}, noted",
    ),
    Rule(
        id="R13",
        label="max-reminders",
        decision="HANDOVER",
        predicate=lambda f, s, c: f.reminder_count >= c.max_reminders_before_human,
        reason=lambda f, s, c: f"{f.reminder_count} reminders sent, handing over to owner",
    ),
    Rule(
        id="R14",
        label="not-due",
        decision="WAIT",
        predicate=lambda f, s, c: f.days_overdue == 0,
        reason=lambda f, s, c: "Not yet due",
    ),
    Rule(
        id="R15",
        label="grace",
        decision="WAIT",
        predicate=lambda f, s, c: f.days_overdue <= c.grace_days,
        reason=lambda f, s, c: "Within grace period",
    ),
    Rule(
        id="R16",
        label="cooldown",
        decision="WAIT",
        predicate=lambda f, s, c: (
            f.hours_since_last_reminder is not None
            and f.hours_since_last_reminder < c.reminder_cooldown_hours
        ),
        reason=lambda f, s, c: (
            f"Reminded {f.hours_since_last_reminder:.0f}h ago; cooldown {c.reminder_cooldown_hours}h"
        ),
    ),
    Rule(
        id="R17",
        label="critical-exposure",
        decision="CRITICAL",
        predicate=lambda f, s, c: (
            f.days_overdue >= c.high_priority_after_days
            and f.due_inr >= c.critical_amount_inr
            and s.category in ("NO_RESPONSE", "HOSTILE")
        ),
        reason=lambda f, s, c: f"{f.days_overdue} days overdue, {f.due_inr} due, no engagement from client",
    ),
    Rule(
        id="R18",
        label="escalate",
        decision="ESCALATE",
        predicate=lambda f, s, c: (
            f.days_overdue >= c.high_priority_after_days
            and f.due_inr >= c.escalate_amount_inr
            and f.unanswered_reminders >= c.min_reminders_before_escalation
        ),
        reason=lambda f, s, c: (
            f"{f.days_overdue} days overdue, {f.due_inr} due, "
            f"{f.unanswered_reminders} reminders unanswered"
        ),
    ),
    Rule(
        id="R19",
        label="high-priority",
        decision="HIGH_PRIORITY",
        predicate=lambda f, s, c: f.days_overdue >= c.high_priority_after_days,
        reason=lambda f, s, c: f"{f.days_overdue} days overdue",
    ),
    Rule(
        id="R20",
        label="followup",
        decision="FOLLOWUP",
        predicate=lambda f, s, c: f.days_overdue >= c.followup_after_days,
        reason=lambda f, s, c: f"{f.days_overdue} days overdue",
    ),
    Rule(
        id="R21",
        label="default-wait",
        decision="WAIT",
        predicate=lambda f, s, c: True,
        reason=lambda f, s, c: "No action needed right now",
    ),
]


def evaluate(facts: InvoiceFacts, signal: ResponseSignal, config: PolicyConfig) -> DecisionResult:
    for rule in RULES:
        if rule.predicate(facts, signal, config):
            return DecisionResult(
                decision=rule.decision,
                rule_id=rule.id,
                reason=rule.reason(facts, signal, config),
            )
    raise AssertionError("no rule matched; R21 default-wait should always match")
