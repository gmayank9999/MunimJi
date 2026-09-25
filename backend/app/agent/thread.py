"""Reads and parses a client's Gmail thread (MunimJi's only two-way client channel -
Slack is internal-only, see docs/swytchcode-notes.md) into GmailMessage objects, and
picks out the ones the agent hasn't reacted to yet."""

import asyncio
import base64
from datetime import UTC, datetime

from app.agent.schemas import GmailMessage
from app.integrations import gmail
from app.swy.executor import CallCtx


def _header(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _find_text_part(part: dict) -> str | None:
    if part.get("mimeType") == "text/plain":
        return part.get("body", {}).get("data")
    for sub_part in part.get("parts") or []:
        data = _find_text_part(sub_part)
        if data:
            return data
    return None


def _decode_body(payload: dict) -> str:
    data = _find_text_part(payload) or payload.get("body", {}).get("data")
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def parse_message(raw: dict, *, client_email: str) -> GmailMessage:
    payload = raw.get("payload", {})
    headers = payload.get("headers", [])
    from_email = _header(headers, "From")
    return GmailMessage(
        message_id=raw["id"],
        thread_id=raw["threadId"],
        from_email=from_email,
        to_email=_header(headers, "To"),
        date=datetime.fromtimestamp(int(raw["internalDate"]) / 1000, tz=UTC),
        subject=_header(headers, "Subject"),
        body=_decode_body(payload),
        is_from_client=client_email.lower() in from_email.lower(),
    )


async def fetch_client_thread(client_email: str, *, ctx: CallCtx) -> list[GmailMessage]:
    """All messages exchanged with this client's address, oldest first."""
    search_result = await gmail.search(f"from:{client_email} OR to:{client_email}", ctx=ctx)
    if not search_result.ok:
        return []
    stubs = search_result.data.get("messages") or []

    details = await asyncio.gather(*(gmail.get_message(stub["id"], ctx=ctx) for stub in stubs))
    messages = [
        parse_message(detail.data, client_email=client_email) for detail in details if detail.ok
    ]
    messages.sort(key=lambda m: m.date)
    return messages


def unseen_client_messages(
    messages: list[GmailMessage], since: datetime | None
) -> list[GmailMessage]:
    """Client messages the agent hasn't interpreted yet (strictly after `since`)."""
    return [
        m for m in messages if m.is_from_client and (since is None or m.date > since)
    ]
