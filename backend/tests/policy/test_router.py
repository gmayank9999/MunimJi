from app.policy.config import load_policy_config
from app.policy.router import FeatureFlags, route
from tests.policy.conftest import make_facts, make_signal

CONFIG = load_policy_config()


def _action_types(actions):
    return [a.action_type for a in actions]


def test_followup_gmail_needs_approval_for_vip():
    facts = make_facts(client_tier="VIP")
    actions = route(facts, make_signal(), "FOLLOWUP", CONFIG)
    gmail = next(a for a in actions if a.action_type == "gmail_reminder")
    assert gmail.needs_approval is True


def test_followup_gmail_no_approval_for_regular():
    facts = make_facts(client_tier="Regular")
    actions = route(facts, make_signal(), "FOLLOWUP", CONFIG)
    gmail = next(a for a in actions if a.action_type == "gmail_reminder")
    assert gmail.needs_approval is False


def test_high_priority_gmail_needs_approval_for_vip_only():
    vip_actions = route(make_facts(client_tier="VIP"), make_signal(), "HIGH_PRIORITY", CONFIG)
    regular_actions = route(make_facts(client_tier="Regular"), make_signal(), "HIGH_PRIORITY", CONFIG)
    assert next(a for a in vip_actions if a.action_type == "gmail_reminder").needs_approval is True
    assert next(a for a in regular_actions if a.action_type == "gmail_reminder").needs_approval is False


def test_escalate_gmail_always_needs_approval_regardless_of_tier():
    for tier in ("VIP", "Regular", "New", "Watchlist"):
        actions = route(make_facts(client_tier=tier), make_signal(), "ESCALATE", CONFIG)
        gmail = next(a for a in actions if a.action_type == "gmail_escalation")
        assert gmail.needs_approval is True


def test_dispute_route_and_reconcile_gmail_always_need_approval():
    dispute_actions = route(make_facts(), make_signal(category="DISPUTE"), "DISPUTE_ROUTE", CONFIG)
    reconcile_actions = route(make_facts(), make_signal(category="CLAIMS_PAID"), "RECONCILE", CONFIG)
    assert next(a for a in dispute_actions if a.action_type == "gmail_acknowledgment").needs_approval is True
    assert next(a for a in reconcile_actions if a.action_type == "gmail_reconcile_request").needs_approval is True


def test_escalate_sms_deferred_in_quiet_hours():
    facts = make_facts(in_quiet_hours=True)
    actions = route(facts, make_signal(), "ESCALATE", CONFIG)
    sms = next(a for a in actions if a.action_type == "twilio_sms_owner")
    assert sms.defer_until is not None


def test_escalate_sms_not_deferred_outside_quiet_hours():
    facts = make_facts(in_quiet_hours=False)
    actions = route(facts, make_signal(), "ESCALATE", CONFIG)
    sms = next(a for a in actions if a.action_type == "twilio_sms_owner")
    assert sms.defer_until is None


def test_flags_off_drops_optional_actions():
    flags = FeatureFlags(sheets=False, twilio=False, calendly=False, stripe_native_reminder=False)
    actions = route(make_facts(), make_signal(), "ESCALATE", CONFIG, flags=flags)
    types = _action_types(actions)
    assert "twilio_sms_owner" not in types
    assert "calendly_link" not in types
    assert "sheets_decision_row" not in types

    followup_actions = route(make_facts(), make_signal(), "FOLLOWUP", CONFIG, flags=flags)
    assert "stripe_invoice_reminder" not in _action_types(followup_actions)


def test_close_includes_jira_close_only_when_ticket_open():
    with_ticket = route(make_facts(open_jira_key="FIN-12"), make_signal(), "CLOSE", CONFIG)
    without_ticket = route(make_facts(open_jira_key=None), make_signal(), "CLOSE", CONFIG)
    assert "jira_close" in _action_types(with_ticket)
    assert "jira_close" not in _action_types(without_ticket)


def test_close_sends_thank_you_only_for_claims_paid():
    verified = route(make_facts(), make_signal(category="CLAIMS_PAID"), "CLOSE", CONFIG)
    plain = route(make_facts(), make_signal(category="NO_RESPONSE"), "CLOSE", CONFIG)
    assert "gmail_thank_you" in _action_types(verified)
    assert "gmail_thank_you" not in _action_types(plain)


def test_critical_proposes_refund_within_threshold():
    signal = make_signal(category="REFUND_REQUEST", refund_amount_inr=4000)
    actions = route(make_facts(), signal, "CRITICAL", CONFIG)
    refund = next((a for a in actions if a.action_type == "stripe_refund"), None)
    assert refund is not None
    assert refund.needs_approval is True


def test_critical_does_not_propose_refund_above_threshold():
    signal = make_signal(category="REFUND_REQUEST", refund_amount_inr=60000)
    actions = route(make_facts(), signal, "CRITICAL", CONFIG)
    assert "stripe_refund" not in _action_types(actions)


def test_handover_never_sends_gmail():
    actions = route(make_facts(), make_signal(), "HANDOVER", CONFIG)
    assert all("gmail" not in a.action_type for a in actions)


def test_idem_key_stable_for_identical_inputs():
    facts = make_facts()
    a1 = route(facts, make_signal(), "FOLLOWUP", CONFIG)
    a2 = route(facts, make_signal(), "FOLLOWUP", CONFIG)
    assert [a.idem_key for a in a1] == [a.idem_key for a in a2]


def test_idem_key_differs_per_invoice():
    a1 = route(make_facts(invoice_id="inv_a"), make_signal(), "FOLLOWUP", CONFIG)
    a2 = route(make_facts(invoice_id="inv_b"), make_signal(), "FOLLOWUP", CONFIG)
    gmail_a = next(a for a in a1 if a.action_type == "gmail_reminder")
    gmail_b = next(a for a in a2 if a.action_type == "gmail_reminder")
    assert gmail_a.idem_key != gmail_b.idem_key


def test_idem_key_differs_per_demo_epoch():
    facts = make_facts()
    a1 = route(facts, make_signal(), "FOLLOWUP", CONFIG, demo_epoch=1)
    a2 = route(facts, make_signal(), "FOLLOWUP", CONFIG, demo_epoch=2)
    gmail_1 = next(a for a in a1 if a.action_type == "gmail_reminder")
    gmail_2 = next(a for a in a2 if a.action_type == "gmail_reminder")
    assert gmail_1.idem_key != gmail_2.idem_key
