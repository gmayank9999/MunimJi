from datetime import datetime

from app.clock import IST
from app.policy.config import load_policy_config
from app.policy.rules import counterfactuals, evaluate
from tests.policy.conftest import make_facts, make_signal

CONFIG = load_policy_config()


def test_grace_period_invoice_counts_down_to_followup():
    # INV-1042: Pinecrest, Rs 8,000, 1 day overdue -> WAIT (grace)
    facts = make_facts(number="INV-1042", client_tier="New", due_inr=8000, days_overdue=1)
    current = evaluate(facts, make_signal(), CONFIG)
    assert current.decision == "WAIT"

    hints = counterfactuals(facts, make_signal(), CONFIG)
    assert any("FOLLOWUP" in h for h in hints)


def test_followup_invoice_counts_up_to_high_priority():
    # INV-1063: Bluepeak, Rs 22,000, 5 days overdue -> FOLLOWUP
    facts = make_facts(number="INV-1063", client_tier="Regular", due_inr=22000, days_overdue=5)
    current = evaluate(facts, make_signal(), CONFIG)
    assert current.decision == "FOLLOWUP"

    hints = counterfactuals(facts, make_signal(), CONFIG)
    assert any("HIGH_PRIORITY" in h for h in hints)


def test_escalate_invoice_downgrades_if_client_promises():
    # INV-1077: Orion, Rs 85,000, 11 days overdue, 2 unanswered reminders -> ESCALATE
    facts = make_facts(
        number="INV-1077", client_tier="Regular", due_inr=85000, days_overdue=11, unanswered_reminders=2
    )
    current = evaluate(facts, make_signal(), CONFIG)
    assert current.decision == "ESCALATE"

    hints = counterfactuals(facts, make_signal(), CONFIG)
    assert any("commits to a payment date" in h for h in hints)


def test_cooldown_wait_hints_at_time_it_ends():
    facts = make_facts(
        days_overdue=5,
        hours_since_last_reminder=20.0,
        as_of=datetime(2026, 9, 25, 10, 0, tzinfo=IST),
    )
    current = evaluate(facts, make_signal(), CONFIG)
    assert current.rule_id == "R16"

    hints = counterfactuals(facts, make_signal(), CONFIG)
    assert any("cooldown ends" in h for h in hints)


def test_no_hints_when_perturbations_do_not_change_a_terminal_decision():
    facts = make_facts(paypal_status="PAID")
    hints = counterfactuals(facts, make_signal(), CONFIG)
    assert hints == []
