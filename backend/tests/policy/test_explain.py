from app.policy.config import load_policy_config
from app.policy.explain import deterministic_reasons, generate_decision_table_markdown
from app.policy.rules import evaluate
from tests.policy.conftest import make_facts, make_signal

CONFIG = load_policy_config()


def test_escalate_reasons_include_days_amount_and_reminders():
    facts = make_facts(days_overdue=11, due_inr=85000, unanswered_reminders=2)
    result = evaluate(facts, make_signal(), CONFIG)
    reasons = deterministic_reasons(facts, make_signal(), result, CONFIG)
    joined = " ".join(reasons)
    assert "11 days overdue" in joined
    assert "85,000" in joined
    assert "2 reminders unanswered" in joined


def test_grace_reasons_mention_grace_period():
    facts = make_facts(days_overdue=1)
    result = evaluate(facts, make_signal(), CONFIG)
    reasons = deterministic_reasons(facts, make_signal(), result, CONFIG)
    assert any("grace period" in r for r in reasons)


def test_reconcile_reasons_mention_no_matching_transaction():
    facts = make_facts(paid_inr=0)
    signal = make_signal(category="CLAIMS_PAID", claimed_reference="UTR412398765012")
    result = evaluate(facts, signal, CONFIG)
    reasons = deterministic_reasons(facts, signal, result, CONFIG)
    joined = " ".join(reasons)
    assert "UTR412398765012" in joined
    assert "no matching transaction" in joined


def test_every_rule_has_a_reason_builder():
    from app.policy.explain import _BUILDERS
    from app.policy.rules import RULES

    for rule in RULES:
        assert rule.id in _BUILDERS


def test_decision_table_markdown_lists_all_rules():
    markdown = generate_decision_table_markdown(CONFIG)
    for i in range(1, 22):
        assert f"R{i:02d}" in markdown
    assert "Escalate threshold" in markdown
