import base64
from datetime import UTC, datetime

from app.agent.schemas import GmailMessage
from app.agent.thread import parse_message, unseen_client_messages


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


SAMPLE_MESSAGE = {
    "id": "msg_1",
    "threadId": "thread_1",
    "internalDate": "1790368555000",
    "payload": {
        "headers": [
            {"name": "From", "value": "Orion Retail <mayankguptawp+orion@gmail.com>"},
            {"name": "To", "value": "kaarigar.studio.demo@gmail.com"},
            {"name": "Subject", "value": "Re: INV-1077"},
        ],
        "mimeType": "text/plain",
        "body": {"data": _b64("We'll pay by Friday.")},
    },
}


def test_parse_message_basic_fields():
    msg = parse_message(SAMPLE_MESSAGE, client_email="mayankguptawp+orion@gmail.com")
    assert msg.message_id == "msg_1"
    assert msg.thread_id == "thread_1"
    assert msg.subject == "Re: INV-1077"
    assert msg.body == "We'll pay by Friday."
    assert msg.is_from_client is True


def test_parse_message_not_from_client():
    msg = parse_message(SAMPLE_MESSAGE, client_email="mayankguptawp+someone-else@gmail.com")
    assert msg.is_from_client is False


def test_parse_message_multipart_body():
    raw = {
        **SAMPLE_MESSAGE,
        "payload": {
            "headers": SAMPLE_MESSAGE["payload"]["headers"],
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64("plain text body")}},
            ],
        },
    }
    msg = parse_message(raw, client_email="mayankguptawp+orion@gmail.com")
    assert msg.body == "plain text body"


def test_parse_message_empty_body_when_no_text_part():
    raw = {**SAMPLE_MESSAGE, "payload": {"headers": [], "mimeType": "multipart/alternative", "parts": []}}
    msg = parse_message(raw, client_email="x@example.com")
    assert msg.body == ""


def _msg(*, is_from_client: bool, date: datetime) -> GmailMessage:
    return GmailMessage(
        message_id="m", thread_id="t", from_email="a", to_email="b",
        date=date, subject="s", body="b", is_from_client=is_from_client,
    )


def test_unseen_client_messages_excludes_agency_messages():
    messages = [
        _msg(is_from_client=True, date=datetime(2026, 9, 1, tzinfo=UTC)),
        _msg(is_from_client=False, date=datetime(2026, 9, 2, tzinfo=UTC)),
    ]
    unseen = unseen_client_messages(messages, since=None)
    assert len(unseen) == 1
    assert unseen[0].is_from_client is True


def test_unseen_client_messages_filters_by_since():
    since = datetime(2026, 9, 1, tzinfo=UTC)
    messages = [
        _msg(is_from_client=True, date=datetime(2026, 8, 30, tzinfo=UTC)),
        _msg(is_from_client=True, date=datetime(2026, 9, 2, tzinfo=UTC)),
    ]
    unseen = unseen_client_messages(messages, since=since)
    assert len(unseen) == 1
    assert unseen[0].date == datetime(2026, 9, 2, tzinfo=UTC)


def test_unseen_client_messages_none_since_returns_all_client_messages():
    messages = [_msg(is_from_client=True, date=datetime(2026, 1, 1, tzinfo=UTC))]
    assert unseen_client_messages(messages, since=None) == messages
