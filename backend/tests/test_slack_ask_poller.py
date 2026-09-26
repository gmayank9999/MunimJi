import pytest

from app.db import Database
from app.reasoning.schemas import IntentClassification
from app.swy.executor import ToolCallResult
from app.workers import slack_ask_poller


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "ask_poller.db"))
    await database.connect()
    yield database
    await database.close()


def _history_result(messages: list[dict]) -> ToolCallResult:
    return ToolCallResult(
        logical="slack.history", canonical_id="slack.conversations.history.list", ok=True,
        data={"messages": messages}, duration_ms=1,
    )


def _fake_history(result: ToolCallResult):
    async def _fake(*args, **kwargs):
        return result

    return _fake


def _fake_post(sink: list[dict]):
    async def _fake(channel, text, *, blocks=None, thread_ts=None, ctx, dry_run=False):
        sink.append({"channel": channel, "text": text, "thread_ts": thread_ts})
        return ToolCallResult(logical="slack.post", canonical_id="x", ok=True, data={}, duration_ms=1)

    return _fake


def _fake_classify(intent: str, args: dict | None = None, reasoning: str = "because"):
    async def _fake(prompt, *, now_ist, llm=None, db=None, cache=False):
        return IntentClassification(intent=intent, args=args or {}, reasoning=reasoning)

    return _fake


async def test_cold_start_seeds_cursor_without_answering(db, monkeypatch):
    posted: list[dict] = []
    monkeypatch.setattr(
        slack_ask_poller.slack, "history",
        _fake_history(_history_result([{"ts": "100.000", "text": "how many payments pending?"}])),
    )
    monkeypatch.setattr(slack_ask_poller.slack, "post", _fake_post(posted))

    answered = await slack_ask_poller.poll_once(db)

    assert answered == 0
    assert posted == []
    assert await db.get_cursor(slack_ask_poller.CURSOR_NAME) == "100.000"


async def test_answers_new_status_question(db, monkeypatch):
    await db.set_cursor(slack_ask_poller.CURSOR_NAME, "100.000")
    posted: list[dict] = []
    monkeypatch.setattr(
        slack_ask_poller.slack, "history",
        _fake_history(_history_result([{"ts": "200.000", "text": "how many payments pending?"}])),
    )
    monkeypatch.setattr(slack_ask_poller.slack, "post", _fake_post(posted))
    monkeypatch.setattr(
        slack_ask_poller, "classify_intent", _fake_classify("status", {"question": "pending count?"})
    )
    monkeypatch.setattr(slack_ask_poller.ask, "answer", lambda question, *, db, today: _const("3 invoices pending"))

    answered = await slack_ask_poller.poll_once(db)

    assert answered == 1
    assert posted == [{"channel": "C0C4DQC0RH9", "text": "3 invoices pending", "thread_ts": "200.000"}]
    assert await db.get_cursor(slack_ask_poller.CURSOR_NAME) == "200.000"


async def _const(value):
    return value


async def test_declines_a_write_intent_instead_of_running_it(db, monkeypatch):
    await db.set_cursor(slack_ask_poller.CURSOR_NAME, "100.000")
    posted: list[dict] = []
    monkeypatch.setattr(
        slack_ask_poller.slack, "history",
        _fake_history(_history_result([{"ts": "200.000", "text": "send all the reminders now"}])),
    )
    monkeypatch.setattr(slack_ask_poller.slack, "post", _fake_post(posted))
    monkeypatch.setattr(slack_ask_poller, "classify_intent", _fake_classify("sweep", {"scope": "all_open"}))

    answered = await slack_ask_poller.poll_once(db)

    assert answered == 1
    assert posted[0]["text"] == slack_ask_poller.DECLINE_MESSAGE


async def test_skips_the_bots_own_messages(db, monkeypatch):
    await db.set_cursor(slack_ask_poller.CURSOR_NAME, "100.000")
    posted: list[dict] = []
    monkeypatch.setattr(
        slack_ask_poller.slack, "history",
        _fake_history(_history_result([{"ts": "200.000", "text": "an answer", "bot_id": "B1"}])),
    )
    monkeypatch.setattr(slack_ask_poller.slack, "post", _fake_post(posted))

    answered = await slack_ask_poller.poll_once(db)

    assert answered == 0
    assert posted == []


async def test_does_not_reanswer_the_boundary_message(db, monkeypatch):
    await db.set_cursor(slack_ask_poller.CURSOR_NAME, "200.000")
    posted: list[dict] = []
    monkeypatch.setattr(
        slack_ask_poller.slack, "history",
        _fake_history(_history_result([{"ts": "200.000", "text": "already answered"}])),
    )
    monkeypatch.setattr(slack_ask_poller.slack, "post", _fake_post(posted))

    answered = await slack_ask_poller.poll_once(db)

    assert answered == 0
    assert posted == []


async def test_failed_slack_history_returns_zero(db, monkeypatch):
    failed = ToolCallResult(logical="slack.history", canonical_id="x", ok=False, error="boom", duration_ms=1)
    monkeypatch.setattr(slack_ask_poller.slack, "history", _fake_history(failed))

    answered = await slack_ask_poller.poll_once(db)
    assert answered == 0
