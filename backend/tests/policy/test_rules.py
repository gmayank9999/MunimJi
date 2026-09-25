from datetime import date, datetime

from app.clock import IST
from app.policy.config import load_policy_config
from app.policy.rules import evaluate
from tests.policy.conftest import make_facts, make_signal

CONFIG = load_policy_config()


def test_r01_paypal_dispute():
    result = evaluate(make_facts(dispute_open=True), make_signal(), CONFIG)
    assert result.rule_id == "R01"
    assert result.decision == "CRITICAL"


def test_r02_refund_request():
    result = evaluate(make_facts(), make_signal(category="REFUND_REQUEST"), CONFIG)
    assert result.rule_id == "R02"
    assert result.decision == "CRITICAL"


def test_r03_paid_close():
    result = evaluate(make_facts(paypal_status="PAID"), make_signal(), CONFIG)
    assert result.rule_id == "R03"
    assert result.decision == "CLOSE"


def test_r03_paid_close_via_zero_due():
    result = evaluate(make_facts(due_inr=0), make_signal(), CONFIG)
    assert result.rule_id == "R03"
    assert result.decision == "CLOSE"


def test_r04_refunded_close():
    result = evaluate(make_facts(paypal_status="REFUNDED"), make_signal(), CONFIG)
    assert result.rule_id == "R04"
    assert result.decision == "CLOSE"


def test_r05_owner_paused():
    facts = make_facts(paused_until=date(2026, 10, 1), as_of=datetime(2026, 9, 25, 10, 0, tzinfo=IST))
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R05"
    assert result.decision == "WAIT"


def test_r06_client_dispute():
    result = evaluate(make_facts(), make_signal(category="DISPUTE", dispute_reason="site is broken"), CONFIG)
    assert result.rule_id == "R06"
    assert result.decision == "DISPUTE_ROUTE"


def test_r07_claims_paid_unverified():
    result = evaluate(make_facts(paid_inr=0), make_signal(category="CLAIMS_PAID"), CONFIG)
    assert result.rule_id == "R07"
    assert result.decision == "RECONCILE"


def test_r08_claims_paid_verified():
    facts = make_facts(paid_inr=5000, due_inr=15000, amount_inr=20000)
    result = evaluate(facts, make_signal(category="CLAIMS_PAID"), CONFIG)
    assert result.rule_id == "R08"
    assert result.decision == "CLOSE"


def test_r09_promise_pending():
    facts = make_facts(promise_status="pending", promise_date=date(2026, 9, 24))
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R09"
    assert result.decision == "WAIT"


def test_r10_promise_broken_big():
    facts = make_facts(promise_status="broken", promise_date=date(2026, 9, 20), due_inr=60000)
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R10"
    assert result.decision == "ESCALATE"


def test_r11_promise_broken_small():
    facts = make_facts(promise_status="broken", promise_date=date(2026, 9, 20), due_inr=20000)
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R11"
    assert result.decision == "HIGH_PRIORITY"


def test_r12_extension_reasonable():
    facts = make_facts(client_tier="Regular", due_date=date(2026, 9, 20))
    result = evaluate(
        facts, make_signal(category="EXTENSION_REQUEST", requested_extension_until=date(2026, 9, 30)), CONFIG
    )
    assert result.rule_id == "R12"
    assert result.decision == "WAIT"


def test_r12_does_not_apply_to_watchlist():
    facts = make_facts(client_tier="Watchlist", due_date=date(2026, 9, 20), days_overdue=1)
    result = evaluate(
        facts, make_signal(category="EXTENSION_REQUEST", requested_extension_until=date(2026, 9, 30)), CONFIG
    )
    assert result.rule_id != "R12"


def test_r13_max_reminders():
    result = evaluate(make_facts(reminder_count=4), make_signal(), CONFIG)
    assert result.rule_id == "R13"
    assert result.decision == "HANDOVER"


def test_r14_not_due():
    result = evaluate(make_facts(days_overdue=0), make_signal(), CONFIG)
    assert result.rule_id == "R14"
    assert result.decision == "WAIT"


def test_r15_grace():
    result = evaluate(make_facts(days_overdue=2), make_signal(), CONFIG)
    assert result.rule_id == "R15"
    assert result.decision == "WAIT"


def test_r16_cooldown():
    facts = make_facts(days_overdue=5, hours_since_last_reminder=20.0)
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R16"
    assert result.decision == "WAIT"


def test_r17_critical_exposure():
    facts = make_facts(days_overdue=10, due_inr=200000)
    result = evaluate(facts, make_signal(category="NO_RESPONSE"), CONFIG)
    assert result.rule_id == "R17"
    assert result.decision == "CRITICAL"


def test_r18_escalate():
    facts = make_facts(days_overdue=10, due_inr=60000, unanswered_reminders=2)
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R18"
    assert result.decision == "ESCALATE"


def test_r19_high_priority():
    facts = make_facts(days_overdue=10, due_inr=20000, unanswered_reminders=0)
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R19"
    assert result.decision == "HIGH_PRIORITY"


def test_r20_followup():
    facts = make_facts(days_overdue=4)
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R20"
    assert result.decision == "FOLLOWUP"


def test_r21_default_wait_with_gapped_config():
    gapped_config = CONFIG.model_copy(update={"grace_days": 1, "followup_after_days": 5})
    facts = make_facts(days_overdue=3)
    result = evaluate(facts, make_signal(), gapped_config)
    assert result.rule_id == "R21"
    assert result.decision == "WAIT"


def test_rule_order_dispute_wins_over_paid_close():
    facts = make_facts(dispute_open=True, paypal_status="PAID")
    result = evaluate(facts, make_signal(), CONFIG)
    assert result.rule_id == "R01"


def test_rule_order_promise_broken_big_wins_over_critical_exposure():
    facts = make_facts(
        promise_status="broken", promise_date=date(2026, 9, 1), days_overdue=10, due_inr=200000
    )
    result = evaluate(facts, make_signal(category="NO_RESPONSE"), CONFIG)
    assert result.rule_id == "R10"
