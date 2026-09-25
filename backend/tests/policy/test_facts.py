from datetime import date, datetime

from app.clock import IST
from app.policy.config import load_policy_config
from app.policy.facts import build_facts

CONFIG = load_policy_config()


def _build(**overrides):
    base = dict(
        invoice_id="inv_1",
        number="INV-1063",
        client_id="c_1",
        client_name="Bluepeak Media",
        client_tier="Regular",
        paypal_status="SENT",
        amount_inr=22000,
        due_inr=22000,
        paid_inr=0,
        invoice_date=date(2026, 9, 10),
        due_date=date(2026, 9, 20),
        as_of=datetime(2026, 9, 25, 10, 0, tzinfo=IST),
        config=CONFIG,
    )
    base.update(overrides)
    return build_facts(**base)


def test_days_overdue_positive_when_past_due():
    f = _build()
    assert f.days_overdue == 5


def test_days_overdue_clamped_to_zero_when_not_yet_due():
    f = _build(due_date=date(2026, 10, 1))
    assert f.days_overdue == 0


def test_days_since_issue():
    f = _build()
    assert f.days_since_issue == 15


def test_is_partially_paid_true_between_zero_and_amount():
    f = _build(paid_inr=5000)
    assert f.is_partially_paid is True


def test_is_partially_paid_false_when_unpaid():
    f = _build(paid_inr=0)
    assert f.is_partially_paid is False


def test_paid_status_zeroes_due_amount():
    f = _build(paypal_status="PAID", due_inr=22000)
    assert f.due_inr == 0


def test_marked_as_paid_zeroes_due_amount():
    f = _build(paypal_status="MARKED_AS_PAID", due_inr=22000)
    assert f.due_inr == 0


def test_reminder_count_and_hours_since_last():
    reminders = [
        datetime(2026, 9, 21, 10, 0, tzinfo=IST),
        datetime(2026, 9, 24, 10, 0, tzinfo=IST),
    ]
    f = _build(reminder_timestamps=reminders)
    assert f.reminder_count == 2
    assert f.hours_since_last_reminder == 24.0


def test_no_reminders_has_none_hours_since_last():
    f = _build()
    assert f.hours_since_last_reminder is None


def test_unanswered_reminders_all_count_when_no_client_reply():
    reminders = [datetime(2026, 9, 21, 10, 0, tzinfo=IST), datetime(2026, 9, 23, 10, 0, tzinfo=IST)]
    f = _build(reminder_timestamps=reminders, last_client_msg_at=None)
    assert f.unanswered_reminders == 2


def test_unanswered_reminders_only_count_after_last_client_message():
    reminders = [datetime(2026, 9, 21, 10, 0, tzinfo=IST), datetime(2026, 9, 24, 10, 0, tzinfo=IST)]
    f = _build(reminder_timestamps=reminders, last_client_msg_at=datetime(2026, 9, 22, 0, 0, tzinfo=IST))
    assert f.unanswered_reminders == 1


def test_promise_status_none_without_promise_date():
    f = _build()
    assert f.promise_status == "none"


def test_promise_status_pending_within_grace():
    f = _build(promise_date=date(2026, 9, 24), as_of=datetime(2026, 9, 25, 10, 0, tzinfo=IST))
    assert f.promise_status == "pending"


def test_promise_status_broken_past_grace():
    f = _build(promise_date=date(2026, 9, 20), as_of=datetime(2026, 9, 25, 10, 0, tzinfo=IST))
    assert f.promise_status == "broken"


def test_promise_status_kept_when_paid():
    f = _build(promise_date=date(2026, 9, 20), paypal_status="PAID")
    assert f.promise_status == "kept"


def test_in_quiet_hours_wraps_midnight():
    late_night = _build(as_of=datetime(2026, 9, 25, 22, 0, tzinfo=IST))
    early_morning = _build(as_of=datetime(2026, 9, 25, 6, 0, tzinfo=IST))
    daytime = _build(as_of=datetime(2026, 9, 25, 12, 0, tzinfo=IST))
    assert late_night.in_quiet_hours is True
    assert early_morning.in_quiet_hours is True
    assert daytime.in_quiet_hours is False


def test_is_business_day_weekday_vs_weekend():
    friday = _build(as_of=datetime(2026, 9, 25, 10, 0, tzinfo=IST))  # Friday
    saturday = _build(as_of=datetime(2026, 9, 26, 10, 0, tzinfo=IST))  # Saturday
    assert friday.is_business_day is True
    assert saturday.is_business_day is False
