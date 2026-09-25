import json
from typing import Any

# swytchcode_runtime.exec's SwytchcodeError.message is the raw combined stdout+stderr
# text: a `[swytchcode exec] request ...` log line, then the classified error as its
# own JSON line, then a `[swytchcode exec] failed ...` log line. `error.details` is not
# reliably populated (observed None even when the JSON line is present), so we parse
# the JSON line out of the message ourselves. See docs/swytchcode-notes.md.

_POLICY_MARKER = 'blocked by policy "'


def extract_error_json(message: str) -> dict[str, Any] | None:
    for line in message.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


class SwytchcodeCallError(Exception):
    """A classified failure from a Swytchcode exec call."""

    def __init__(self, message: str, category: str, raw: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.raw = raw or {}

    @property
    def policy_blocked(self) -> bool:
        return self.category == "policy_denied"

    @property
    def policy_id(self) -> str | None:
        if _POLICY_MARKER not in self.message:
            return None
        rest = self.message.split(_POLICY_MARKER, 1)[1]
        return rest.split('"', 1)[0]


def classify(exc: Exception) -> SwytchcodeCallError:
    """Classify a swytchcode_runtime.SwytchcodeError into category + policy id."""
    raw_message = getattr(exc, "message", None) or str(exc)
    data = extract_error_json(raw_message) or {}
    category = data.get("category", "internal")
    message = data.get("error", raw_message)
    return SwytchcodeCallError(message, category, raw=data)
