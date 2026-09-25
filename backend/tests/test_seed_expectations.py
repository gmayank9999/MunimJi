"""All 18 seeded demo invoices (IMPLEMENTATION_PLAN.md Section 18.2) -> expected decisions.

Facts are built directly (not via build_facts/live data) to keep this offline and fast,
mirroring each invoice's story at clock offset 0 ("D" = today).
"""

from collections import Counter
from datetime import date, datetime, timedelta

from app.clock import IST
from app.policy.config import load_policy_config
from app.policy.rules import evaluate
from tests.policy.conftest import make_facts, make_signal

CONFIG = load_policy_config()
D = datetime(2026, 9, 25, 10, 0, tzinfo=IST)  # "today"


def d_minus(days: int) -> date:
    return (D - timedelta(days=days)).date()


def d_plus(days: int) -> date:
    return (D + timedelta(days=days)).date()


CASES = [
    # (number, expected_decision, expected_rule_id, facts_overrides, signal_overrides)
    ("INV-1031", "CLOSE", "R03", dict(client_tier="VIP", payment_status="PAID", amount_inr=15000, due_inr=0), {}),
    ("INV-1034", "CLOSE", "R03", dict(client_tier="Regular", payment_status="PAID", amount_inr=12000, due_inr=0), {}),
    (
        "INV-1038", "WAIT", "R14",
        dict(client_tier="New", payment_status="SENT", amount_inr=18000, due_inr=18000, days_overdue=0),
        {},
    ),
    (
        "INV-1042", "WAIT", "R15",
        dict(client_tier="New", payment_status="SENT", amount_inr=8000, due_inr=8000, days_overdue=1),
        {},
    ),
    (
        "INV-1049", "HIGH_PRIORITY", "R19",
        dict(
            client_tier="VIP", payment_status="SENT", amount_inr=40000, due_inr=40000,
            days_overdue=8, reminder_count=1, hours_since_last_reminder=96.0, unanswered_reminders=1,
        ),
        {},
    ),
    (
        "INV-1053", "WAIT", "R09",
        dict(
            client_tier="Regular", payment_status="SENT", amount_inr=26000, due_inr=26000,
            days_overdue=6, reminder_count=1, hours_since_last_reminder=72.0, unanswered_reminders=0,
            promise_date=d_plus(2), promise_status="pending", last_client_msg_at=D,
        ),
        dict(category="PROMISE_TO_PAY", promise_date=d_plus(2)),
    ),
    (
        "INV-1056", "HIGH_PRIORITY", "R11",
        dict(
            client_tier="Watchlist", payment_status="SENT", amount_inr=35000, due_inr=35000,
            days_overdue=12, reminder_count=2, promise_date=d_minus(4), promise_status="broken",
        ),
        {},
    ),
    (
        "INV-1060", "RECONCILE", "R07",
        dict(
            client_tier="VIP", payment_status="SENT", amount_inr=30000, due_inr=30000, paid_inr=0,
            days_overdue=4, reminder_count=1,
        ),
        dict(category="CLAIMS_PAID", claimed_payment_date=d_minus(2), claimed_reference="UTR412398765012"),
    ),
    (
        "INV-1063", "FOLLOWUP", "R20",
        dict(client_tier="Regular", payment_status="SENT", amount_inr=22000, due_inr=22000, days_overdue=5),
        {},
    ),
    (
        "INV-1066", "WAIT", "R12",
        dict(
            client_tier="New", payment_status="SENT", amount_inr=14000, due_inr=14000,
            days_overdue=9, reminder_count=1, due_date=d_minus(9),
        ),
        dict(category="EXTENSION_REQUEST", requested_extension_until=d_plus(5)),
    ),
    (
        "INV-1070", "CRITICAL", "R01",
        dict(
            client_tier="VIP", payment_status="PAID", amount_inr=60000, due_inr=0,
            days_overdue=15, dispute_open=True,
        ),
        {},
    ),
    (
        "INV-1072", "WAIT", "R16",
        dict(
            client_tier="Watchlist", payment_status="SENT", amount_inr=9000, due_inr=9000,
            days_overdue=4, reminder_count=1, hours_since_last_reminder=20.0,
        ),
        {},
    ),
    (
        "INV-1074", "DISPUTE_ROUTE", "R06",
        dict(
            client_tier="Regular", payment_status="SENT", amount_inr=48000, due_inr=48000,
            days_overdue=6, reminder_count=1,
        ),
        dict(category="DISPUTE", dispute_reason="Mobile checkout still breaks on iPhones"),
    ),
    (
        "INV-1077", "ESCALATE", "R18",
        dict(
            client_tier="Regular", payment_status="SENT", amount_inr=85000, due_inr=85000,
            days_overdue=11, reminder_count=2, unanswered_reminders=2, hours_since_last_reminder=72.0,
        ),
        {},
    ),
    (
        "INV-1079", "CRITICAL", "R17",
        dict(
            client_tier="Regular", payment_status="SENT", amount_inr=180000, due_inr=180000,
            days_overdue=9, reminder_count=1,
        ),
        {},
    ),
    (
        "INV-1081", "CRITICAL", "R02",
        dict(
            client_tier="New", payment_status="PAID", amount_inr=4000, due_inr=0, paid_inr=4000,
            days_overdue=12,
        ),
        dict(category="REFUND_REQUEST", refund_amount_inr=4000),
    ),
    (
        "INV-1084", "HANDOVER", "R13",
        dict(
            client_tier="Watchlist", payment_status="SENT", amount_inr=27000, due_inr=27000,
            days_overdue=25, reminder_count=4,
        ),
        {},
    ),
    (
        "INV-1086", "FOLLOWUP", "R20",
        dict(client_tier="VIP", payment_status="SENT", amount_inr=22000, due_inr=22000, days_overdue=3),
        {},
    ),
]

EXPECTED_TOTALS = {
    "CLOSE": 2, "WAIT": 5, "FOLLOWUP": 2, "HIGH_PRIORITY": 2, "ESCALATE": 1,
    "CRITICAL": 3, "DISPUTE_ROUTE": 1, "RECONCILE": 1, "HANDOVER": 1,
}


def test_all_18_seeded_invoices_match_expected_decision_and_rule():
    failures = []
    for number, expected_decision, expected_rule, facts_overrides, signal_overrides in CASES:
        facts = make_facts(number=number, as_of=D, **facts_overrides)
        signal = make_signal(**signal_overrides)
        result = evaluate(facts, signal, CONFIG)
        if result.decision != expected_decision or result.rule_id != expected_rule:
            failures.append(
                f"{number}: expected {expected_decision}/{expected_rule}, "
                f"got {result.decision}/{result.rule_id}"
            )
    assert not failures, "\n".join(failures)


def test_18_scanned_and_expected_totals():
    assert len(CASES) == 18
    decisions = (
        evaluate(make_facts(number=n, as_of=D, **fo), make_signal(**so), CONFIG).decision
        for n, _, _, fo, so in CASES
    )
    assert dict(Counter(decisions)) == EXPECTED_TOTALS
