from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# pydantic-settings parses .env into this Settings object only - it never exports to
# os.environ. Other modules that need raw env vars directly (e.g. allowlist.py's
# "${VAR}" substitution) need this done explicitly.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: str = ""
    # Groq's catalog moved on since these were first picked (llama-3.3-70b-versatile and
    # llama-3.1-8b-instant both now 404 as model_not_found) - openai/gpt-oss-* is what's
    # actually available and confirmed working with structured/tool-calling output.
    model_reasoning: str = "openai/gpt-oss-120b"
    model_fast: str = "openai/gpt-oss-20b"

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
    feature_jira: bool = True  # off in this demo's .env - see docs/swytchcode-notes.md for the 401 root cause
    feature_stripe_native_reminder: bool = True

    # Off in tests: the app lifespan's background pollers (slack_poller,
    # slack_ask_poller) make real Slack calls on their own timer, and TestClient(app)
    # runs the full lifespan for every test - unmocked, unbounded network calls in the
    # background of hundreds of unrelated tests caused real, hard-to-diagnose hangs
    # (cancel() on teardown doesn't reliably interrupt a call already in flight).
    enable_background_pollers: bool = True

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
