from math import log10

from pydantic import BaseModel

from app.policy.config import PolicyConfig
from app.policy.facts import InvoiceFacts, ResponseSignal

SIGNAL_RISK: dict[str, float] = {
    "NO_RESPONSE": 0.8,
    "ACKNOWLEDGED": 0.3,
    "PROMISE_TO_PAY": 0.2,
    "DISPUTE": 0.6,
    "CLAIMS_PAID": 0.5,
    "EXTENSION_REQUEST": 0.4,
    "REFUND_REQUEST": 0.7,
    "HOSTILE": 1.0,
    "OTHER": 0.5,
}

TIER_RISK: dict[str, float] = {"VIP": 0.2, "Regular": 0.5, "New": 0.7, "Watchlist": 1.0}


class SeverityResult(BaseModel):
    score: int
    band: str
    jira_priority: str
    breakdown: dict[str, float]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _signal_risk(category: str, promise_status: str) -> float:
    if category == "PROMISE_TO_PAY" and promise_status == "broken":
        return 1.0
    return SIGNAL_RISK[category]


def score_severity(
    facts: InvoiceFacts, signal: ResponseSignal, config: PolicyConfig
) -> SeverityResult:
    weights = config.severity_weights

    aging = weights.aging * _clamp(facts.days_overdue / 21, 0, 1)

    exposure_raw = _clamp(log10(max(facts.due_inr, 1)) - 3, 0, 2.3)
    exposure = weights.exposure * exposure_raw / 2.3

    reminders_ignored = weights.reminders_ignored * _clamp(facts.unanswered_reminders / 3, 0, 1)

    client_signal = weights.client_signal * _signal_risk(signal.category, facts.promise_status)

    tier = weights.tier * TIER_RISK[facts.client_tier]

    breakdown = {
        "aging": aging,
        "exposure": exposure,
        "reminders_ignored": reminders_ignored,
        "client_signal": client_signal,
        "tier": tier,
    }
    raw = sum(breakdown.values())
    score = round(_clamp(raw * config.tier_multipliers[facts.client_tier], 0, 100))
    band = config.band_for(score)

    return SeverityResult(score=score, band=band.label, jira_priority=band.jira, breakdown=breakdown)
