from datetime import timedelta

from app.clock import Clock, real_now_ist


def test_zero_offset_matches_real_now():
    c = Clock(offset_days=0)
    delta = c.now() - real_now_ist()
    assert abs(delta.total_seconds()) < 2


def test_offset_shifts_forward():
    c = Clock(offset_days=7)
    delta = c.now() - real_now_ist()
    assert timedelta(days=7) - timedelta(seconds=2) < delta < timedelta(days=7) + timedelta(seconds=2)


def test_offset_shifts_backward():
    c = Clock(offset_days=-3)
    delta = real_now_ist() - c.now()
    assert timedelta(days=3) - timedelta(seconds=2) < delta < timedelta(days=3) + timedelta(seconds=2)


def test_today_returns_date_in_ist():
    c = Clock(offset_days=0)
    assert c.today() == c.now().date()


def test_with_offset_returns_new_clock_unmutated():
    c = Clock(offset_days=0)
    shifted = c.with_offset(5)
    assert c.offset_days == 0
    assert shifted.offset_days == 5


def test_now_has_ist_tzinfo():
    c = Clock()
    assert c.now().tzinfo is not None
    assert c.now().utcoffset() == timedelta(hours=5, minutes=30)
