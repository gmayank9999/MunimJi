from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_BUSINESS_PATH = Path(__file__).resolve().parents[1] / "config" / "business.yaml"


class BusinessConfig(BaseModel):
    business_name: str
    business_type: str
    owner_name: str
    owner_title: str
    sender_name: str
    signature: str
    tone_guide: str
    currency_display: str
    stripe_currency: str
    fx_inr_per_usd: float
    payment_link_note: str


def load_business_config(path: Path | str = DEFAULT_BUSINESS_PATH) -> BusinessConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return BusinessConfig.model_validate(data)


@lru_cache
def get_business_config() -> BusinessConfig:
    return load_business_config()
