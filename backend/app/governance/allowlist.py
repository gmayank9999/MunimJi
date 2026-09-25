import fnmatch
import os
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_ALLOWLIST_PATH = Path(__file__).resolve().parents[2] / "config" / "allowlist.yaml"


class Allowlist(BaseModel):
    email_recipients_patterns: list[str] = []
    sms_recipients: list[str] = []

    def is_email_allowed(self, email: str) -> bool:
        return any(fnmatch.fnmatch(email.lower(), p.lower()) for p in self.email_recipients_patterns)

    def is_sms_allowed(self, phone: str) -> bool:
        return phone in self.sms_recipients


def _substitute_env(value: str) -> str:
    if value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1], "")
    return value


def load_allowlist(path: Path | str = DEFAULT_ALLOWLIST_PATH) -> Allowlist:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Allowlist(
        email_recipients_patterns=data.get("email_recipients_patterns", []),
        sms_recipients=[_substitute_env(v) for v in data.get("sms_recipients", [])],
    )
