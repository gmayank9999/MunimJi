from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: str = ""
    model_reasoning: str = "llama-3.3-70b-versatile"
    model_fast: str = "llama-3.1-8b-instant"

    swytchcode_token: str = ""
    swytchcode_bin: str = ""

    business_email: str = "kaarigar.studio.demo@gmail.com"
    owner_phone_e164: str = ""
    twilio_from_e164: str = ""
    twilio_account_sid: str = ""
    slack_approver_user_id: str = ""
    timezone: str = "Asia/Kolkata"

    app_db_path: str = "./data/munimji.db"
    checkpoint_db_path: str = "./data/checkpoints.db"

    feature_sheets: bool = True
    feature_twilio: bool = True
    feature_calendly: bool = False  # Calendly bundle is broken in the Swytchcode registry; see tool_registry.yaml
    feature_paypal_native_reminder: bool = True

    demo_mode: bool = True
    demo_epoch: int = 1
    feed_order: Literal["story", "exposure_desc", "due_asc"] = "story"
    replay_mode: Literal["off", "record", "replay"] = "off"
    clock_offset_days: int = 0
    extension_key: str = "change-me-long-random"
    extension_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
