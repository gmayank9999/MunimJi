from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def real_now_ist() -> datetime:
    return datetime.now(IST)


class Clock:
    """Time-Machine aware clock: real IST time shifted by a fixed offset in days."""

    def __init__(self, offset_days: int = 0):
        self.offset_days = offset_days

    def now(self) -> datetime:
        return real_now_ist() + timedelta(days=self.offset_days)

    def today(self) -> date:
        return self.now().date()

    def with_offset(self, offset_days: int) -> "Clock":
        return Clock(offset_days=offset_days)


DEFAULT_CLOCK = Clock(offset_days=0)


def now(offset_days: int = 0) -> datetime:
    return Clock(offset_days=offset_days).now()
