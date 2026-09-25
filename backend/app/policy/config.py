from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "policy.yaml"


class SeverityWeights(BaseModel):
    aging: float
    exposure: float
    reminders_ignored: float
    client_signal: float
    tier: float


class SeverityBand(BaseModel):
    min: int
    max: int
    label: str
    jira: str


class QuietHours(BaseModel):
    start: str
    end: str


class PolicyConfig(BaseModel):
    grace_days: int
    followup_after_days: int
    high_priority_after_days: int
    escalate_amount_inr: int
    critical_amount_inr: int
    min_reminders_before_escalation: int
    reminder_cooldown_hours: int
    promise_grace_days: int
    max_reminders_before_human: int
    quiet_hours: QuietHours
    business_days_only_for_email: bool
    tier_multipliers: dict[str, float]
    severity_weights: SeverityWeights
    severity_bands: list[SeverityBand]
    refund_auto_propose_max_inr: int

    def band_for(self, score: int) -> SeverityBand:
        for band in self.severity_bands:
            if band.min <= score <= band.max:
                return band
        return self.severity_bands[-1]


def load_policy_config(path: Path | str = DEFAULT_POLICY_PATH) -> PolicyConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PolicyConfig.model_validate(data)


@lru_cache
def get_policy_config() -> PolicyConfig:
    return load_policy_config()
