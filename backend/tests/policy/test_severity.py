from hypothesis import given
from hypothesis import strategies as st

from app.policy.config import load_policy_config
from app.policy.severity import score_severity
from tests.policy.conftest import make_facts, make_signal

CONFIG = load_policy_config()


def test_no_response_scores_higher_than_acknowledged():
    facts = make_facts(days_overdue=5, unanswered_reminders=1)
    no_response = score_severity(facts, make_signal(category="NO_RESPONSE"), CONFIG)
    acknowledged = score_severity(facts, make_signal(category="ACKNOWLEDGED"), CONFIG)
    assert no_response.score > acknowledged.score


def test_broken_promise_scores_higher_than_pending_promise():
    pending = make_facts(promise_status="pending")
    broken = make_facts(promise_status="broken")
    pending_result = score_severity(pending, make_signal(category="PROMISE_TO_PAY"), CONFIG)
    broken_result = score_severity(broken, make_signal(category="PROMISE_TO_PAY"), CONFIG)
    assert broken_result.score > pending_result.score


def test_exposure_component_zero_at_low_amount():
    facts = make_facts(due_inr=1000)
    result = score_severity(facts, make_signal(), CONFIG)
    assert result.breakdown["exposure"] == 0


def test_exposure_component_maxed_at_two_lakh():
    facts = make_facts(due_inr=200000)
    result = score_severity(facts, make_signal(), CONFIG)
    assert result.breakdown["exposure"] == CONFIG.severity_weights.exposure


def test_vip_scores_lower_than_watchlist_for_identical_facts():
    vip = make_facts(client_tier="VIP")
    watchlist = make_facts(client_tier="Watchlist")
    vip_result = score_severity(vip, make_signal(), CONFIG)
    watch_result = score_severity(watchlist, make_signal(), CONFIG)
    assert vip_result.score < watch_result.score


def test_band_for_score_in_critical_range():
    facts = make_facts(days_overdue=21, due_inr=200000, unanswered_reminders=3, client_tier="Watchlist")
    result = score_severity(facts, make_signal(category="HOSTILE"), CONFIG)
    assert result.band == "Critical"
    assert result.score >= 70


def test_score_never_exceeds_100_or_drops_below_zero():
    facts = make_facts(days_overdue=999, due_inr=99_999_999, unanswered_reminders=999, client_tier="Watchlist")
    result = score_severity(facts, make_signal(category="HOSTILE"), CONFIG)
    assert 0 <= result.score <= 100


@given(base_days=st.integers(min_value=0, max_value=60), extra_days=st.integers(min_value=0, max_value=30))
def test_severity_monotonic_in_days_overdue(base_days, extra_days):
    lower = make_facts(days_overdue=base_days)
    higher = make_facts(days_overdue=base_days + extra_days)
    lower_score = score_severity(lower, make_signal(), CONFIG).score
    higher_score = score_severity(higher, make_signal(), CONFIG).score
    assert higher_score >= lower_score


@given(
    base_due=st.integers(min_value=100, max_value=500_000),
    extra_due=st.integers(min_value=0, max_value=200_000),
)
def test_severity_monotonic_in_due_amount(base_due, extra_due):
    lower = make_facts(due_inr=base_due)
    higher = make_facts(due_inr=base_due + extra_due)
    lower_score = score_severity(lower, make_signal(), CONFIG).score
    higher_score = score_severity(higher, make_signal(), CONFIG).score
    assert higher_score >= lower_score


@given(
    days=st.integers(min_value=0, max_value=60),
    due=st.integers(min_value=100, max_value=500_000),
)
def test_vip_never_scores_above_watchlist(days, due):
    vip = make_facts(client_tier="VIP", days_overdue=days, due_inr=due)
    watchlist = make_facts(client_tier="Watchlist", days_overdue=days, due_inr=due)
    vip_score = score_severity(vip, make_signal(), CONFIG).score
    watch_score = score_severity(watchlist, make_signal(), CONFIG).score
    assert vip_score <= watch_score
